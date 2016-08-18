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


### logdb.py

Performs a bulk operation on