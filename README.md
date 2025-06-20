# Sinitaivas Live

[![sinitaivas-live](https://github.com/letiziaia/sinitaivas-live/actions/workflows/validate.yml/badge.svg)](https://github.com/letiziaia/sinitaivas-live/actions/workflows/validate.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![codecov](https://codecov.io/gh/letiziaia/sinitaivas-live/graph/badge.svg?token=EY3Ha33SAF)](https://codecov.io/gh/letiziaia/sinitaivas-live)
[![DOI](https://zenodo.org/badge/1000111410.svg)](https://doi.org/10.5281/zenodo.15641656)

Welcome to the real-time data collection of the entire [Bluesky](https://bsky.app/)!
Here below you find more info on the pipeline for the data collection and on how to use the data for research and analysis.

(_sinitaivas_ means _bluesky_ in Finnish)

If you use the code or instructions in this repository in your research, please cite it using the DOI above (see [https://zenodo.org/records/15641657](https://zenodo.org/records/15641657)). Here's the latest publications that have used data collected with _Sinitaivas Live_ code:

- [![arXiv](https://img.shields.io/badge/arXiv-2506.03443-b31b1b.svg)](https://www.arxiv.org/pdf/2506.03443) Salloum A., Quelle D., Iannucci L., Bovet A., Kivelä M. ["Politics and Polarization on Bluesky"](https://www.arxiv.org/pdf/2506.03443)

## Table of Contents

- [Bluesky Firehose](#bluesky-firehose)
- [Data format](#data-format)
- [Events](#events)
- [Data partitioning](#data-partitioning)
- [How to get started](#how-to-get-started)
- [Contributing](#contributing)
- [License](#license)
- [Contacts](#contacts)
- [Last Updated](#last-updated)

[BlueSky Firehose](https://docs.bsky.app/docs/advanced-guides/firehose) is an authenticated stream of real-time events from the social media (i.e. user updates). We have developed a data streaming service that collects real-time data from Blueksky Firehose and provides a continuous stream of **all** data to a desired local directory. All data means exactly _all data_: all users, all languages, all activities that are possible on the social.

The data is collected by keeping an active subscription to Bluesky Firehose API (see `/ops` for how to run the collection as a managed service in unix environment).

Live stream means a continuous, real-time transmission of data as it is generated. In the context of the Bluesky Firehose, this means that we are collecting and providing data in real-time as it happens on the Bluesky social media platform. This includes all user activities, updates, and interactions that occur on the platform at the moment when our subscription to Bluesky Firehose API is up and running.

The data is collected immediately as events occur on the platform. There is no significant delay between the occurrence of an event and its availability in the data stream.

### FAQ

1. **If I Start the Collection Now, Will I Get Data from Year 2023?**
   The live stream data collection collects data moving forward from the point in time when it is started. The live stream only includes data from the point of initiation onwards. With this pipeline, you can not get data from a time when the subscription was off. In general, the role of a live streaming API is not to provide data from the past.

2. **Can I Get Historical Data Before the Collection Started?**
   No, at least not from Bluesky Firehose. However, Bluesky provides an API from which you can also download activities that happened in the past. But the historical collection is not implemented here.

3. **What Format is the Data in?**
   The data is collected as NDJSON (Newline Delimited JSON) and stored as is or later compressed by gzip (see `/ops`). In either case, each event is stored on a separate line.

4. **Is the Data Anonymized?**
   No. The data is collected as raw, exactly as it comes after decoding the message from Bluesky Firehose.

5. **What Happens If the Collection Crashes?**
   If the data collection crashes or is restarted, it tries to resume from the latest known position of the cursor, minimizing data loss.

## Data Format

Bluesky Firehose streams events as individual messages that are encoded according to AT Protocol and its lexicon. This means that data needs to be decoded upon arrival. This part of the work (ie. decoding the CBOR event) is taken care by the service. The raw (but now decoded) data is what we store in ndjson files. The reason for choosing json is because it is schemaless but still allows for easy parsing and querying.

Each event is stored in a different line (ie. you can count the rows in a file to know the number of events).

The json format differs between events. You are welcome to explore the data to see which fields appear in the event type you are interested in. Additionally, each event includes metadata such as:

- `action`: from `action` attribute of `RepoOp` object, one of `create`, `update`, or `delete`

- `author`: from `repo` attribute of `Commit` object, the repo this event comes from

- `cid`: from `cid` attribute of `RepoOp`, the new record CID for creates and updates (appears as `None` for deletions)

- `collected_at`: UTC timestamp of our data collection (timestamp of when our service received and saved the event)

- `commit_time`: from `time` attribute of `Commit` object, the UTC timestamp of the event in Bluesky Firehose (timestamp of when this message was originally broadcasted)

- `createdAt`: UTC timestamp of the event in Bluesky (the social). These are generally assumed to represent the original time of posting, but clients are allowed to insert any value. This flexibility enables things like importing microblogging posts from other platforms, or migrating content between Bluesky servers. But it does open up the possibility of shenanigans. For example, if you chose a far-future timestamp, that record will always sort at the top of chronologically-sorted lists of posts. ([source](https://docs.bsky.app/docs/advanced-guides/timestamps#createdat))

- `rev`: from `rev` attribute of `Commit` object, the rev of the emitted commit

- `seq`: from `seq` attribute of `Commit` object, the monotonically increasing cursor position (stream sequence number of this message), which can be used to order the events by arrival

- `since`: from `since` attribute of `Commit` object, the rev of the last emitted commit from this repo (if any)

- `type`: from `collection` attribute of `AtUri` object (equivalent to `$type`), the collection name (type of event)

A Commit message represents an update of repository state. Note that empty commits are allowed, which include no repo data changes, but an update to `rev` and `signature`. Repo operations from the Commit message appear as RepoOp blocks.

See below for more specifications of the events.

**Note:** All timestamps are UTC in standard [Zulu format](https://pilotinstitute.com/what-is-zulu-time/). You can recognize them from the ISO format "YYYY-MM-DDTHH:MM:SSZ", which can be lexicographycally sorted. Always storing datetime values in UTC on the server side / database side is a commonly recognized best practice in software engineering. Should you want to get back the data collection timestamp in your local time, you can do so by using existing database functions or your favorite programming language.

## Events

Bluesky Firehose streams the following native event types (`app.bsky.*)`:

- `app.bsky.actor.profile`
- `app.bsky.feed.generator`
- `app.bsky.feed.like`
- `app.bsky.feed.longpost`
- `app.bsky.feed.post`
- `app.bsky.feed.postgate`
- `app.bsky.feed.repost`
- `app.bsky.feed.share`
- `app.bsky.feed.threadgate`
- `app.bsky.graph.block`
- `app.bsky.graph.follow`
- `app.bsky.graph.list`
- `app.bsky.graph.listblock`
- `app.bsky.graph.listitem`
- `app.bsky.graph.starterpack`
- `app.bsky.labeler.service`

You can filter them under the `type` (or `$type`) field in each event. Besides these native events, other events are also possible (they start with something else than `app.bsky`).

Each event is also associated with one `action`:

- `create`
- `delete`
- `update`

This means that you can for example find all newly created posts by writing a query with filter `action = 'create' and type = 'app.bsky.feed.post'`.

Most events also present the following fields:

- `author`: the DID (Decentralized Identifier) of the user who performed the action. A DID is a type of identifier that enables verifiable, self-sovereign digital identities in decentralized or blockchain systems
- `uri`: Uniform Resource Identifier that uniquely identify the data resource
- `cid`: Content Identifier (a concept from the AT Protocol (atproto), which is used by Bluesky, to provide a unique identifier for content in decentralized systems
- `subject`: typically a json object of its own, but can also be the DID of another user. Usually represents the target of the action

Beware that only events that are newly created posts contain the field `text`. This means that any event related to like, repost, or similar does not contain the text of the post that is referencing, but only its `uri`. On the other hand, the `uri` of a post also includes the DID of its author: `at://did:plc:exampledidstring/resource`.

Some (but not all) of newly created posts also contain the field `langs`, which is an array of language codes related to the post text.

## Data partitioning

Data partitioning is a very basic yet essential data engineering approach to optimize the storage, retrieval, and processing of very large datasets. The idea is to divide a large dataset into smaller, more manageable pieces, called partitions. Partitions are defined by specific criteria, such as time ranges, geographical regions, or other logical divisions. Each partition is stored separately, but collectively they represent the entire dataset.

In our case, partitions are defined by UTC time. The first level of partitioning is the UTC day of data collection. You will see them as directories under the destionation you indicated for the collection. Each directory contains 24 files (if complete), that are named with the UTC date and hour of data collection:

- `1999-01-01/`
  - `1999-01-01T00.ndjson.gz`
  - `...`

### Why?

Data partitioning improves performance, manageability, and scalability of data storage and retrieval, assuming that partitions are decently defined. In our case, the rationale behind data partitioning is that you are able to fully inspect one single file (aka partition) without the need to spin up cloud or cluster resources. In fact, you should be able to download, uncompress, and open one single partition on your local machine with any text editor. While the entire streaming data collection will never fit in RAM, having partitions means you can easily jump around the dataset and eyeball it.

Once you have decided what part of the data you want to extract from the raw file, having partitions also means that we can define efficient queries on the raw data (yes, we can write queries on these json files). Whichever engine you use to run the queries, you can significantly reduce the amount of data scanned (and therefore the time for data processing) by querying only the relevant partitions or by using partitions already as filters. Partitioning also allows for parallel processing of data, where multiple partitions can be processed simultaneously, improving overall performance. In general, decent partitioning leads to faster query performance. For example, you can use wildcards to query all data for one specific day (`/1999-01-01/*.ndjson.gz`) or all data for one specific month (`/1999-01-*/*.ndjson.gz`) without the need for your query to scan the rest of the data.

Besides this, partitions are also easier to manage, back up, and restore compared to a single large dataset, they help in managing and scaling large datasets, and make it easier to manage data lifecycle (e.g., data retention policies or archiving).

## How to get started

_Step 0:_ Start the data collection. See [RUNBOOK.md](RUNBOOK.md) for details.

_Step 1:_ Randomly choose one file and familiarize yourself with the data format. You can also refer to Bluesky documentation.

_Step 2:_ Download and install a database client or a library that supports handling large-scale data and SQL queries. Some options are:

- [DuckDB (either client or library)](https://duckdb.org/)
- [ClickHouse](https://clickhouse.com/clickhouse)
- [Apache Spark](https://spark.apache.org/)
- ...

_Step 3:_ Save your version of preprocessed data

## Contributing

Please read our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributions, code style, and pull request workflow.

## License

See [LICENSE.md](LICENSE.md).

[![CC BY-SA 4.0](https://licensebuttons.net/l/by-sa/4.0/88x31.png)](http://creativecommons.org/licenses/by-sa/4.0/)

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
