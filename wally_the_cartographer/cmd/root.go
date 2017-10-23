package cmd

import (
	"os"
	"context"
	"log"

	"github.com/pkg/errors"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"
	"github.com/google/go-github/github"
	"golang.org/x/oauth2"

)

const ACCESS_TOKEN = "TODO: rather pass through config file or ENV"

var (
	versionFlag bool
)

var RootCmd = &cobra.Command{
	Use:   "wally_the_cartographer",
	Short: "Auto merge bot for googlecartographer/",
	Long: "Auto merge bot for googlecartographer/",
	PersistentPreRun: func(cmd *cobra.Command, args []string) {
		if versionFlag {
			log.Print("1.0.0")
			os.Exit(0)
		}
	},
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx := context.Background()

		ts := oauth2.StaticTokenSource(
			&oauth2.Token{AccessToken: ACCESS_TOKEN},
		)
		tc := oauth2.NewClient(ctx, ts)
		client := github.NewClient(tc)
		opt := &github.NotificationListOptions{All: true}
		notifications, _, err := client.Activity.ListNotifications(ctx, opt)
		if err != nil {
			log.Panic(err)
		}
		for _, e := range notifications {
			log.Printf("e: %v\n", e)
		}

		return errors.New("No command provided")
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
