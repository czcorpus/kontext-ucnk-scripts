kontext-ucnk-scripts
====================

This project contains a bunch of Python scripts used to support in-house installations
of KonText as used by the Czech National Corpus.


Plug-Ins
--------

### ucnk\_remote\_auth2

* *db.sql* creates all the required additional tables and triggers
* *syncdb.py* provides a one-way synchronization between our information system and KonText database
  * the script should be from *cron* or via *Celery Beat*


### live\_attributes

This section contains scripts for extraction of structural attributes data from the vertical file.
