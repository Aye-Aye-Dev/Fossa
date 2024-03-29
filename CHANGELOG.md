# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased
 
### Added
- nothing

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

