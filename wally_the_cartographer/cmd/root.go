package cmd

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/google/go-github/github"
	"github.com/pkg/errors"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"
	"golang.org/x/oauth2"
)

var (
	versionFlag bool
)

func prettyDump(prefix string, val interface{}) {
	blob, _ := json.MarshalIndent(val, "", "   ")
	log.Printf("%s: %s\n", prefix, string(blob))
}

// Configuration is read from config.json in the current work directory.
type Configuration struct {
	// List of "orga/repo" this bot should care for.
	ManagedRepositories []string `json:"managed_repositories"`

	// Github token for authentication.
	GithubToken string `json:"github_token"`

	// The slug of the team that this bot will accept comments from.
	TeamSlug string `json:"team_slug"`

	// Data directory that will contained cloned repos and state.json.
	Datadir string `json:"datadir"`
}

// PullRequestState contains the last seen state of a PR from the last run.
type PullRequestState struct {
	NumComments int    `json:"num_comments"`
	LastSHASeen string `json:"last_sha_seen"`
}

// WorkItem is a merge that the bot is pushing through.
type WorkItem struct {
	Repo string `json:"repo"`
	Pr   int    `json:"pr"`
}

// RepositoryState is the bot state for a repo from the last run.
type RepositoryState struct {
	WorkQueue    []WorkItem                `json:"work_queue"`
	PullRequests map[int]*PullRequestState `json:"pull_requests"`
}

// State is saved in datadir/state.json and connects the last run to the next run.
type State struct {
	Repositories map[string]*RepositoryState `json:"repositories"`
}

// ReadState parses 'state.json'.
func ReadState(datadir string) (*State, error) {
	state := State{
		Repositories: make(map[string]*RepositoryState),
	}
	p := path.Join(datadir, "state.json")
	if _, err := os.Stat(p); os.IsNotExist(err) {
		return &state, nil
	}
	dat, err := ioutil.ReadFile(p)
	if err != nil {
		return nil, err
	}

	err = json.Unmarshal([]byte(dat), &state)
	if err != nil {
		return nil, err
	}
	return &state, nil
}

// WriteState writes 'state.json'.
func WriteState(state *State, datadir string) error {
	blob, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return err
	}
	return ioutil.WriteFile(path.Join(datadir, "state.json"), blob, 0644)
}

// GitHubRepositoryFromString takes "onwer/repo" and returns it as a struct.
func GitHubRepositoryFromString(s string) *github.Repository {
	parts := strings.SplitN(s, "/", 2)
	return &github.Repository{Owner: &github.User{Login: &parts[0]}, Name: &parts[1]}
}

// ReadConfiguration reads 'config.json'.
func ReadConfiguration() (*Configuration, error) {
	dat, err := ioutil.ReadFile("config.json")
	if err != nil {
		return nil, err
	}

	config := Configuration{}
	err = json.Unmarshal([]byte(dat), &config)
	if err != nil {
		return nil, err
	}
	return &config, nil
}

// RunCommand runs a command, echoes its commandline and stdout into 'log'.
func RunCommand(workdir string, log io.Writer, args ...string) error {
	fmt.Fprintf(log, " $ %s [%s]\n", strings.Join(args, " "), workdir)
	return RunCommandSilent(workdir, log, args...)
}

// RunCommandSilent is like RunCommand, but does not echo the commandline.
func RunCommandSilent(workdir string, log io.Writer, args ...string) error {
	c := exec.Command(args[0], args[1:]...)
	c.Stdout = log
	c.Stderr = log
	c.Dir = workdir
	return c.Run()
}

// CaptureCommand runs a command and returns its output.
func CaptureCommand(workdir string, args ...string) (string, error) {
	var logOutput bytes.Buffer
	c := exec.Command(args[0], args[1:]...)
	c.Stdout = &logOutput
	c.Stderr = &logOutput
	c.Dir = workdir
	err := c.Run()
	return strings.TrimSpace(logOutput.String()), err
}

func cloneRepository(repo *github.Repository, datadir string, log io.Writer) error {
	fmt.Fprintf(log, "=> Cloning %s/%s\n", *repo.Owner.Login, *repo.Name)
	return RunCommand(datadir, log, "git", "clone", fmt.Sprintf("https://github.com/%s/%s", *repo.Owner.Login, *repo.Name))
}

func checkoutBranch(repo *github.Repository, datadir string, log io.Writer, localBranch string) error {
	fmt.Fprintf(log, " => Switching to branch %s.\n", localBranch)
	if err := RunCommand(path.Join(datadir, *repo.Name), log, "git", "reset", "--hard", "HEAD"); err != nil {
		return err
	}
	if err := RunCommand(path.Join(datadir, *repo.Name), log, "git", "clean", "-fd"); err != nil {
		return err
	}
	return RunCommand(path.Join(datadir, *repo.Name), log, "git", "checkout", localBranch)
}

func pull(repo *github.Repository, datadir string, log io.Writer) error {
	return RunCommand(path.Join(datadir, *repo.Name), log, "git", "pull")
}

func forkAndCheckout(repo *github.Repository, datadir string, log io.Writer, localBranch string, branch *github.PullRequestBranch) error {
	if err := RunCommand(path.Join(datadir, *repo.Name), log, "git", "branch", "--track",
		localBranch, fmt.Sprintf("%s/%s", *branch.Repo.Owner.Login, *branch.Ref)); err != nil {
		return err
	}
	return checkoutBranch(repo, datadir, log, localBranch)
}

func checkoutRemoteBranch(repo *github.Repository, datadir string, log io.Writer, localBranch string, branch *github.PullRequestBranch) error {
	fmt.Fprintf(log, " => Checking out %s/%s as local branch %s.\n", *branch.Repo.Owner.Login, *branch.Ref, localBranch)
	remote := fmt.Sprintf("git@github.com:%s/%s.git", *branch.Repo.Owner.Login, *branch.Repo.Name)
	_ = RunCommand(path.Join(datadir, *repo.Name), log, "git", "remote", "add", *branch.Repo.Owner.Login, remote)
	if err := RunCommand(path.Join(datadir, *repo.Name), log, "git", "fetch", *branch.Repo.Owner.Login); err != nil {
		return err
	}

	if err := forkAndCheckout(repo, datadir, log, localBranch, branch); err != nil {
		return err
	}

	if err := RunCommand(path.Join(datadir, *repo.Name), log, "git", "pull", "--force"); err != nil {
		return err
	}
	return nil
}

func getHeadSHA(repo *github.Repository, datadir string) (string, error) {
	sha, err := CaptureCommand(path.Join(datadir, *repo.Name), "git", "rev-parse", "--verify", "HEAD")
	if err != nil {
		return "", err
	}
	return sha, nil
}

func abandonBranch(repo *github.Repository, datadir string, log io.Writer, localBranch string) error {
	fmt.Fprintf(log, " => Abandoning branch %s.\n", localBranch)
	if err := checkoutBranch(repo, datadir, log, "master"); err != nil {
		return err
	}
	if err := RunCommand(path.Join(datadir, *repo.Name), log, "git", "branch", "-D", localBranch); err != nil {
		return err
	}
	return nil
}

func switchToAndUpdateMaster(repo *github.Repository, datadir string, log io.Writer) error {
	if err := checkoutBranch(repo, datadir, log, "master"); err != nil {
		return err
	}
	if err := pull(repo, datadir, log); err != nil {
		return err
	}
	return nil
}

func mergeMaster(repo *github.Repository, datadir string, log io.Writer) error {
	fmt.Fprint(log, " => merge master.\n")
	return RunCommand(path.Join(datadir, *repo.Name), log, "git", "merge", "master")
}

func postCommentToPr(ctx context.Context, client *github.Client, repo *github.Repository, pr int, comment string) error {
	log.Printf("Posting comment to %s/%s#%d: %v\n", *repo.Owner.Login, *repo.Name, pr, comment)
	_, _, err := client.Issues.CreateComment(ctx, *repo.Owner.Login, *repo.Name, pr, &github.IssueComment{
		Body: &comment,
	})
	return err
}

func handleWorkItem(ctx context.Context, state *PullRequestState, client *github.Client, pullRequest *github.PullRequest, repo *github.Repository, datadir string, log io.Writer) (bool, error) {
	fmt.Fprintf(log, "=> handle work item: PR %d on %s/%s.\n", pullRequest.GetNumber(), *repo.Owner.Login, *repo.Name)
	if err := switchToAndUpdateMaster(repo, datadir, log); err != nil {
		return true, err
	}
	localBranch := fmt.Sprintf("pr_%d", pullRequest.GetNumber())
	if err := checkoutRemoteBranch(repo, datadir, log, localBranch, pullRequest.Head); err != nil {
		return true, err
	}
	defer abandonBranch(repo, datadir, log, localBranch)

	// TODO(hrapp): Only attempt this if the branch is marked as mergeable by GitHub
	if err := mergeMaster(repo, datadir, log); err != nil {
		return true, err
	}

	if err := runClangFormat(repo, datadir, log); err != nil {
		return true, err
	}

	if err := RunCommand(path.Join(datadir, *repo.Name), log, "git", "push", "--force", *pullRequest.Head.Repo.Owner.Login,
		fmt.Sprintf("HEAD:%s", *pullRequest.Head.Ref)); err != nil {
		return true, err
	}

	newSHA, err := getHeadSHA(repo, datadir)
	if err != nil {
		return true, err
	}

	// We changed the HEAD SHA. Travis needs to rerun, so we cannot
	// make progress now, but the work item is also not yet done.
	if newSHA != state.LastSHASeen {
		state.LastSHASeen = newSHA
		return false, nil
	}

	combinedStatus, _, err := client.Repositories.GetCombinedStatus(ctx, *repo.Owner.Login, *repo.Name, *pullRequest.Head.SHA, nil)
	if err != nil {
		return true, err
	}
	if combinedStatus.GetState() == "pending" {
		// Travis is probably still running. Retry next round.
		fmt.Fprintln(log, "Check statuses are pending. Retrying next time.")
		return false, nil
	}
	if combinedStatus.GetState() != "success" {
		if err := postCommentToPr(ctx, client, repo, pullRequest.GetNumber(),
			fmt.Sprintf("Refusing to merge, since the combined checks state is %s",
				combinedStatus.GetState())); err != nil {
			return true, err
		}
		return true, nil
	}

	msg := fmt.Sprintf("%s", strings.TrimSpace(pullRequest.GetBody()))
	_, _, err = client.PullRequests.Merge(ctx, *repo.Owner.Login, *repo.Name, pullRequest.GetNumber(), msg,
		&github.PullRequestOptions{
			SHA:         state.LastSHASeen,
			MergeMethod: "squash",
		})
	if err != nil {
		return true, err
	}
	return true, nil
}

func keepPRPristine(pullRequest *github.PullRequest, repo *github.Repository, datadir string, log io.Writer) (string, error) {
	if err := switchToAndUpdateMaster(repo, datadir, log); err != nil {
		return "", err
	}
	localBranch := fmt.Sprintf("pr_%d", pullRequest.GetNumber())
	if err := checkoutRemoteBranch(repo, datadir, log, localBranch, pullRequest.Head); err != nil {
		return "", err
	}
	defer abandonBranch(repo, datadir, log, localBranch)

	if err := runClangFormat(repo, datadir, log); err != nil {
		return "", err
	}

	if err := RunCommand(path.Join(datadir, *repo.Name), log, "git", "push", "--force", *pullRequest.Head.Repo.Owner.Login,
		fmt.Sprintf("HEAD:%s", *pullRequest.Head.Ref)); err != nil {
		return "", err
	}

	newSHA, err := getHeadSHA(repo, datadir)
	if err != nil {
		return "", err
	}

	return newSHA, nil
}

func checkNewCommentsForCommands(ctx context.Context, repositoryState *RepositoryState, prState *PullRequestState,
	client *github.Client, userName string, teamID int, repo *github.Repository, prNum int) error {
	comments, _, err := client.Issues.ListComments(ctx, *repo.Owner.Login, *repo.Name, prNum, &github.IssueListCommentsOptions{})
	if err != nil {
		return err
	}

	lastNumComments := prState.NumComments
	if lastNumComments > len(comments) {
		lastNumComments = len(comments)
	}

	mergeRegex, err := regexp.Compile("(?m:^@" + userName + `\s*merge$)`)
	if err != nil {
		log.Fatalf("Could not compile regex: %v", err)
	}

	for _, comment := range comments[lastNumComments:] {
		if len(mergeRegex.FindString(*comment.Body)) == 0 {
			continue
		}

		membership, response, err := client.Organizations.GetTeamMembership(ctx, teamID, *comment.User.Login)
		// If a user is not in the group, the API returns an error (not found) We have to investigate the status code
		// to know.
		if (err != nil && response.StatusCode == 404) || (err == nil && *membership.State != "active") {
			log.Printf("User %s is not in our team. Ignoring merge request.", *comment.User.Login)
			continue
		}
		if err != nil {
			return err
		}

		repositoryState.WorkQueue = append(repositoryState.WorkQueue, WorkItem{
			Repo: fmt.Sprintf("%s/%s", *repo.Owner.Login, *repo.Name),
			Pr:   prNum,
		})
		_ = postCommentToPr(ctx, client, repo, prNum,
			fmt.Sprintf("Merge requested by authorized user %s. Merge queue now has a length of %d.",
				*comment.User.Login,
				len(repositoryState.WorkQueue)))
		// We ignore all further comments on this PR and will never look at them.
		break
	}
	prState.NumComments = len(comments)
	return nil
}

func handleRepo(ctx context.Context, client *github.Client, userName string, teamID int, repoName string, datadir string, state *State) error {
	repo := GitHubRepositoryFromString(repoName)
	if _, ok := state.Repositories[repoName]; !ok {
		state.Repositories[repoName] = &RepositoryState{
			WorkQueue:    []WorkItem{},
			PullRequests: make(map[int]*PullRequestState),
		}
	}
	repositoryState := state.Repositories[repoName]

	// Handle all WorkItems.
	for len(repositoryState.WorkQueue) != 0 {
		workItem := repositoryState.WorkQueue[0]
		// TODO(hrapp): Only do this if no further comments have been made and last_sha_seen has not changed.
		// TODO(hrapp): Check if the PR is still open.
		pullRequest, _, err := client.PullRequests.Get(ctx, *repo.Owner.Login, *repo.Name, workItem.Pr)
		if err != nil {
			return err
		}

		var logOutput bytes.Buffer
		logWriter := io.MultiWriter(&logOutput, os.Stdout)
		done, err := handleWorkItem(ctx, repositoryState.PullRequests[workItem.Pr], client, pullRequest, repo, datadir, logWriter)
		if done {
			repositoryState.WorkQueue = repositoryState.WorkQueue[1:]
		}
		if err != nil {
			_ = postCommentToPr(ctx, client, repo, pullRequest.GetNumber(),
				fmt.Sprintf("Error: %v\n\nLog:\n~~~\n%s\n~~~", err, logOutput.String()))
			return err
		}
		if err := WriteState(state, datadir); err != nil {
			return err
		}
		if !done {
			// Did some work, but is not done. We have to check again next run of the tool.
			break
		}
	}

	// Look for new comments on PullRequests.
	pullRequests, _, err := client.PullRequests.List(ctx, *repo.Owner.Login, *repo.Name, &github.PullRequestListOptions{})
	if err != nil {
		return err
	}

	for _, pullRequest := range pullRequests {
		log.Printf("=> handle pull request: PR %d on %s/%s.\n", pullRequest.GetNumber(), *repo.Owner.Login, *repo.Name)
		prNum := pullRequest.GetNumber()
		prState := repositoryState.PullRequests[prNum]
		if prState == nil {
			prState = &PullRequestState{}
			repositoryState.PullRequests[prNum] = prState
		}

		newSHA, err := keepPRPristine(pullRequest, repo, datadir, os.Stdout)
		if err != nil {
			return err
		}

		if newSHA != prState.LastSHASeen {
			prState.LastSHASeen = newSHA
			continue
		}
		prState.LastSHASeen = newSHA

		if err := checkNewCommentsForCommands(ctx, repositoryState, prState, client, userName, teamID, repo, prNum); err != nil {
			return err
		}
	}
	return nil
}

func ensureAllReposAreCloned(managedRepositories []string, datadir string) error {
	var logOutput bytes.Buffer
	logWriter := io.MultiWriter(&logOutput, os.Stdout)
	for _, repoName := range managedRepositories {
		repo := GitHubRepositoryFromString(repoName)
		p := path.Join(datadir, *repo.Name)
		if _, err := os.Stat(p); os.IsNotExist(err) {
			err := cloneRepository(repo, datadir, logWriter)
			if err != nil {
				fmt.Fprint(&logOutput, err)
				return err
			}
		}
	}
	return nil
}

// runClangFormat reformats the code base by running clang-format. This might change files on disk.
func runClangFormat(repo *github.Repository, datadir string, logWriter io.Writer) error {
	fmt.Fprint(logWriter, " => Running clang-format on all *.cc and *.h files\n")
	workdir := path.Join(datadir, *repo.Name)
	err := filepath.Walk(workdir, func(rootPath string, info os.FileInfo, err error) error {
		if info.IsDir() {
			return nil
		}
		ext := filepath.Ext(rootPath)
		if ext == ".cc" || ext == ".h" {
			relPath, err := filepath.Rel(workdir, rootPath)
			if err != nil {
				log.Panicf(
					"Could not make %s relative to %s. This should be impossible in this context.",
					rootPath, workdir)
			}
			err = RunCommandSilent(workdir, logWriter, "clang-format", "-i", "-style=Google", relPath)
			if err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		return err
	}
	// We ignoring errors in commit, since if the clang-format run did not change
	// anything, the commit will error.
	_ = RunCommand(workdir, logWriter, "git", "commit", "-am", "Ran clang-format.")
	return nil
}

var RootCmd = &cobra.Command{
	Use:   "wally_the_cartographer",
	Short: "Auto merge bot for googlecartographer organization.",
	Long:  "Auto merge bot for googlecartographer organization.",
	PersistentPreRun: func(cmd *cobra.Command, args []string) {
		if versionFlag {
			log.Print("1.0.0")
			os.Exit(0)
		}
	},
	RunE: func(cmd *cobra.Command, args []string) error {
		config, err := ReadConfiguration()
		_ = os.Mkdir(config.Datadir, 0755)

		if err := ensureAllReposAreCloned(config.ManagedRepositories, config.Datadir); err != nil {
			return err
		}

		state, err := ReadState(config.Datadir)
		if err != nil {
			return err
		}

		ctx := context.Background()
		tc := oauth2.NewClient(ctx, oauth2.StaticTokenSource(
			&oauth2.Token{AccessToken: config.GithubToken},
		))
		client := github.NewClient(tc)

		// Get my username.
		me, _, err := client.Users.Get(ctx, "")
		if err != nil {
			return err
		}

		// Get the ID of the controlling team.
		teamParts := strings.SplitN(config.TeamSlug, "/", 2)
		teams, _, err := client.Organizations.ListTeams(ctx, teamParts[0], nil /* ListOptions */)
		if err != nil {
			return err
		}
		teamID := 0
		for _, team := range teams {
			if *team.Slug == teamParts[1] {
				teamID = *team.ID
				break
			}
		}
		if teamID == 0 {
			return fmt.Errorf("The group %s was not found.", config.TeamSlug)
		}

		// TODO(hrapp): Our state file contains pull requests that were long closed. Clean them up.
		for _, repoName := range config.ManagedRepositories {
			err := handleRepo(ctx, client, *me.Login, teamID, repoName, config.Datadir, state)
			if err != nil {
				log.Printf("Failed to handle repo %s: %v. Continuing.", repoName, err)
			}
		}

		if err := WriteState(state, config.Datadir); err != nil {
			return err
		}
		return nil
	},
}

func Execute() {
	if err := RootCmd.Execute(); err != nil {
		os.Exit(-1)
	}
}

func init() {
	err := viper.BindPFlag("verbose", RootCmd.PersistentFlags().Lookup("verbose"))
	if err != nil {
		log.Fatal(errors.Wrap(err, "Cannot bind verbose flag"))
	}
	RootCmd.PersistentFlags().BoolVar(&versionFlag, "version", false, "Print version and exit")
}
