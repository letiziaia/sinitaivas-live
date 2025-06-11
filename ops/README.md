# sinitaivas-live as a Monitored Service

If you have a Linux server or VM, you can use the scripts in this folder to run the data collection as a `systemd` managed service and monitor it.

The service definition needs to be stored under `/etc/systemd/system`, as it is custom in Unix systems. Modify the template `sinitaivas-live.service` and save the file under the correct path.

Then, you need to register and start the service:

```{bash}
systemctl daemon-reload
systemctl start sinitaivas-live
systemctl enable sinitaivas-live
```

The first command reloads the systemd manager configuration (in case the service file was just created or modified). The second and third command start the service and enable the service to start on boot.

After starting the service, you should also check its status.

```{bash}
systemctl status sinitaivas-live.service
```

The service is actively monitored and also has autorestart within 5 seconds. If the service crashes or is restared, it tries to restart from the latest known position of the cursor, which minimizes the data loss.

If, despite this, you find yourself in need of restarting the service, you can do so from terminal
(same instructions as above).

Otherwise, the data stream is continuous and ongoing, and the service runs 24/7.

## Cron Jobs

### What does _actively monitored_ mean?

The `sinitaivas-live` service has [structured logging](https://www.sumologic.com/glossary/structured-logging/) in place. You can use `monitoring.sh` and the `crontab.template` to define a job that runs every 20 minutes and queries the latest log entry to check that the service is running (ie. not stale or stuck, not in error state). Should the cron job see a log timestamp that is too old or an error in the logs, it will automatically restart the service. The state of the cron job can be received by email, together with the action taken by the monitoring task after the log query. To edit your cron jobs:

```{bash}
crontab -e
```

then save and exit.

### Data Archive

The service dumps data from Bluesky Firehose as one json line per event in partitioned files (see data description below). You can use `gzip_previous_hour.sh` and the `crontab.template` to automatically gzip files when complete.

### Data Sync

The `crontab.template` also defines one job to sync up gzipped data via ssh from the directory of collection to another location. Note that the `rsync` cron job does not delete the raw data from the place of collection. If you need to clean up data after `rsync`, you can define another script (e.g. `delete_folders.sh`) and add another cron job to run daily. Make sure to allow enough time for disaster recovery, should the sync start to fail.

Our pipeline is meant to batch the sync to your directory only once per hour. Should you need more frequent sync, you can ask for help or advice to the contacts below.

## Manual Ops

### How to deploy a new version of the service

As a rule, the `main` branch of the repo is the one running on the VM.

If you implement changes to the source code, you should add also relevant unit tests and finally squash-merge the feature or fix to the `main` branch of the GitHub repo of the system.

After merging to main, you want to deploy the changes. First, `cd` to the directory where the source code is on your local machine:

```{bash}
cd sinitaivas-live/

git status
```

The output of `git status` should be similar to this one:

```
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
        modified:   Pipfile.lock

Untracked files:
  (use "git add <file>..." to include in what will be committed)
        delete_daily_folder.sh
        monitoring.sh

no changes added to commit (use "git add" and/or "git commit -a")
```

You want to stash the current version of the locked env, pull the new changes, relock the env:

```{bash}
git stash push -m "stash Pipfile.lock changes" Pipfile.lock

git pull

pipenv shell

pipenv update --dev
```

After the last command has completed successfully and the new locked environment is created, you can restart the service:

```{bash}
sudo systemctl restart sinitaivas-live.service
```

Finally, check that the service is up and running. You can check this from the service status and by tailing the latest data file or the logs.

## Contacts

If you still have questions, want some more tips how to get started, or want to say that this does not make any sense and the entire setup should be changed, you can reach out:

- Letizia Iannucci

  [![Email](https://img.shields.io/badge/Email-letizia.iannucci@aalto.fi-green?style=flat-square&logo=gmail&logoColor=FFFFFF)](mailto:letizia.iannucci@aalto.fi)

  [![GitHub](https://img.shields.io/badge/GitHub-letiziaia-blue?logo=github)](https://github.com/letiziaia)

  [![Bluesky](https://img.shields.io/badge/Bluesky-@letiziaian.bsky.social-darkblue)](https://bsky.app/profile/letiziaian.bsky.social)

  [![Telegram](https://img.shields.io/badge/Telegram-@letiletizia-blue?logo=telegram)](https://t.me/letiletizia)

  [![X (Twitter)](https://img.shields.io/badge/X-@leetiletizia-blue?logo=x&logoColor=white)](https://twitter.com/leetiletizia)

## Last Updated

2025-06-11
