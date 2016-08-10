# kontext-ucnk-scripts

This project contains a bunch of Python scripts used to support in-house installations
of KonText as used by the Czech National Corpus.

## General

### deploy.py

A script for updating/reverting sources of a running KonText instance

Deploying the latest version from a git repository (defined in *deploy.json*):

```bash
> python deploy.py deploy
```

Showing all the versions used for deployment:

```bash
> python deploy.py list
```

Reinstalling an existing archived instance:

```bash
> python deploy.py deploy 2016-08-10-11-12-37

> python deploy.py deploy 2016-08-10
```

An archive ID (e.g. *2016-08-10-11-12-37*) can be entered in partial form - as a 
prefix (e.g. *2016-08-10*). As long as there is no ambiguity in the entry, the script
is able to fetch a matching archive ID.

## Plug-Ins

### ucnk\_remote\_auth2

* *db.sql* creates all the required additional tables and triggers
* *syncdb.py* provides a one-way synchronization between our information system and KonText database
  * the script should be from *cron* or via *Celery Beat*


### live\_attributes

This section contains scripts for extraction of structural attributes data from the vertical file.
