# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased
 
### Added
- nothing

## [0.0.31] - 2024-07-09
### Changed
- DEBUG log messages around channel conditions to reduce how often they are logged
- best efforts to cleanly shutdown connection to RabbitMQ as this was producing a disturning log message.
- RabbitMqProcessPool to honour number of processes passed. This can be used to rate limit the number of running sub-tasks by using .partition_plea(..)

## [0.0.30] - 2024-05-20
### Changed
- tidied log messages, reduced repeating log messages at controller level

## [0.0.29] - 2024-05-18
### Changed
- internal timeout when waiting for capacity
- RabbitMx.callback_on_processing_complete to use separate rabbit mq client

### Fixed
- with work around when task count can exceed node capacity

### Added
- better clean-up when task with RabbitMq connection is garbage collected

## [0.0.28] - 2024-05-17
### Changed
- .submit_task to have a timeout. This allows RabbitMQ heartbeats to be processed. It was a problem when a node had no capacity and had long running tasks

### Fixed
- a couple of unnecessary sleeps when tasks move between RabbitMq and the governor
- task complete callback wasn't closing the rabbitmq connection
- blocking connections should explicitly call rabbit_mq.connection.process_data_events

## [0.0.27] - 2024-05-16
### Changed
- RabbitMx.callback_on_processing_complete to not close the channel as this appears to be shared within the process
- BasicPikaClient.parameters.blocked_connection_timeout - if this is a problem there will be proper exceptions raised from here on.
 
## [0.0.26] - 2024-05-16
### Changed
- explicit close to RabbitMq connections.

## [0.0.25] - 2024-05-15
### Fixed
- blocking condition when a long running task on a node without available processing capacity. Instea
d reduce the chance of a blocking condition by checking for capacity first.

## [0.0.24] - 2024-05-14
### Fixed
- "Stream connection lost: BrokenPipeError(32, 'Broken pipe')" from RabbitMq with long running tasks
where ACK was too slow.

## [0.0.23] - 2024-05-13
### Added
- CPU_TASK_RATIO to config options

## [0.0.22] - 2024-04-26
### Fixed
- missing test for in flight task id on subtask fail

## [0.0.21] - 2024-04-23
### Changed
- oops, RabbitMq shouldn't have been using auto-ack, wrong tradeoff, not reliable enough

## [0.0.20] - 2024-04-22
### Added
- reduced log outputs when waiting on tasks
- extra details on tasks that are being waited on

### Fixed
- removed stray rabbit_mq.channel.start_consuming() call, not needed in blocking iterator

## [0.0.19] - 2024-04-22
### Added
- improvement around task acceptance stampede, really needs a semaphore

### Changed
- RabbitMx.run_forever to restart on connection failure

## [0.0.18] - 2024-04-22
### Fixed
- was passing empty arguments in main loop on inactivity timeout

## [0.0.17] - 2024-04-22
### Fixed
- was passing empty arguments in main loop on inactivity timeout

## [0.0.16] - 2024-04-22
### Fixed
- failure to return after subtasks complete

## [0.0.15] - 2024-04-16
### Fixed
- RabbitMQ was prefetching all the work tasks making it impossible to change the number of workers after a task is start.

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

