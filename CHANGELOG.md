# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased
 
### Added
- nothing

## [0.0.14] - 2024-04-15
### Changed
- broker and governor's :meth:`sub_task` to dramatically reduce the chance of a node accepting task
s over it's maximum or rejecting tasks when not yet at capacity. There is still a small race condition but
 the new approach is enough for now.

### Fixed
- api's /node_info/ was attempting to serialise a callback method

## [0.0.13] - 2024-04-03
### Added
- retry on subtask fails to RabbitMqProcessPool

## [0.0.12] - 2024-04-03
### Added
- integration tests. Just local multiprocess Processes - it spits out a lot of rubbish. Maybe docker
next for this.
- some integration tests for expected runtime behaviour
- signal based kill of running ETL processes when governor is shutdown
- governor shutdown method which is run via a signal (so it can happen before gunicorn shutdown) or with gunicorn's 'on_exit' hook
- task details page to web interface
- task status attrib across API and web pages

### Changed
- create_app to also accept a dictionary config. Useful for the integration tests
- AbstractIsolatedProcessor to propagate info about failed subtasks to the parent task
- web interface layout - simplified, better layout for tracebacks and task dicts

## [0.0.11] - 2024-03-27
### Changed
- RabbitMqProcessPool.run_subtasks to support upsteam Aye-aye change

## [0.0.10] - 2024-03-26
### Added
- details on currently running tasks to web view
- task_id and _metadata section on submit task via API
- task details page including 'task_status' field

### Changed
- task_id is created in api view's submit task - this makes it possible to track a task from submission.

### Fixed
- missing args in TaskFailed in AbstractIsolatedProcessor

## [0.0.9] - 2024-03-25
### Changed
- AbstractIsolatedProcessor now uses model_construction_kwargs and partition_initialise_kwargs as per updates in upsteam Ayeaye

## [0.0.8] - 2024-03-21
### Changed
- BasicPikaClient to sit around waiting if it can't connect to RabbitMq broker

## [0.0.7] - 2024-03-18
### Fixed
- can't serialise 'method' in API node_info endpoint

## [0.0.6] - 2024-03-18
### Added
- node_info API endpoint - same info as the existing web page

## [0.0.5] - 2024-03-07
### Fixed
- missing `BaseConfig` in distribution again

## [0.0.4] - 2024-03-06
### Fixed
- missing `BaseConfig` in distribution

## [0.0.3] - 2024-03-06
### Fixed
- missing tools

### Changed
- renamed 'run_forever' to 'run_fossa'

### Added
- BaseConfig as top level module
- Alternative way to pass a config to run_forever

## [0.0.2] - 2024-03-05
### Added
- Layout to make this work as a package

## [0.0.1] - 2024-03-05
### Added
- Fossa is added to Pypi
- This code has been under casual development since May 19 2022

