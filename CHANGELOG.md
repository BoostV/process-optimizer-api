# Changelog

## [v2.2.0](https://github.com/BoostV/process-optimizer-api/tree/v2.2.0)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v2.1.1...v2.2.0)

**Implemented enhancements:**

- Show expected minimum in objective function [\#53](https://github.com/BoostV/process-optimizer-api/issues/53)

**Merged pull requests:**

- Read plot\_objective "pars" from extras [\#54](https://github.com/BoostV/process-optimizer-api/pull/54) ([langdal](https://github.com/langdal))

## [v2.1.1](https://github.com/BoostV/process-optimizer-api/tree/v2.1.1) (2023-02-06)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v2.1.0...v2.1.1)

**Closed issues:**

- Deap 1.3.1 lead to error [\#51](https://github.com/BoostV/process-optimizer-api/issues/51)
- Allow deselection of plotting [\#46](https://github.com/BoostV/process-optimizer-api/issues/46)

**Merged pull requests:**

- Pin dependency for ProcessOptimizer [\#52](https://github.com/BoostV/process-optimizer-api/pull/52) ([langdal](https://github.com/langdal))
- Bump waitress from 2.1.1 to 2.1.2 [\#49](https://github.com/BoostV/process-optimizer-api/pull/49) ([dependabot[bot]](https://github.com/apps/dependabot))
- Option for no plot [\#47](https://github.com/BoostV/process-optimizer-api/pull/47) ([SRFU-NN](https://github.com/SRFU-NN))
- Bump waitress from 2.0.0 to 2.1.1 [\#35](https://github.com/BoostV/process-optimizer-api/pull/35) ([dependabot[bot]](https://github.com/apps/dependabot))
- Bump pillow from 8.3.2 to 9.0.1 [\#34](https://github.com/BoostV/process-optimizer-api/pull/34) ([dependabot[bot]](https://github.com/apps/dependabot))

## [v2.1.0](https://github.com/BoostV/process-optimizer-api/tree/v2.1.0) (2022-04-28)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v2.0.1...v2.1.0)

**Implemented enhancements:**

- Return 400 instead of 500 [\#39](https://github.com/BoostV/process-optimizer-api/issues/39)
- Add CORS [\#41](https://github.com/BoostV/process-optimizer-api/pull/41) ([lasseborly](https://github.com/lasseborly))

**Fixed bugs:**

- Update swagger post example data [\#40](https://github.com/BoostV/process-optimizer-api/issues/40)

**Closed issues:**

- Show confidence interval [\#36](https://github.com/BoostV/process-optimizer-api/issues/36)

**Merged pull requests:**

- Return error message instead of throwing exception [\#43](https://github.com/BoostV/process-optimizer-api/pull/43) ([langdal](https://github.com/langdal))
- Update to process\_result in optimizer.py [\#37](https://github.com/BoostV/process-optimizer-api/pull/37) ([abbl-DTI](https://github.com/abbl-DTI))

## [v2.0.1](https://github.com/BoostV/process-optimizer-api/tree/v2.0.1) (2022-03-29)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v2.0.0...v2.0.1)

**Fixed bugs:**

- API fails when using less than N\_points data points [\#33](https://github.com/BoostV/process-optimizer-api/issues/33)

## [v2.0.0](https://github.com/BoostV/process-optimizer-api/tree/v2.0.0) (2022-03-29)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v1.4.1...v2.0.0)

**Implemented enhancements:**

- Feature/multi objective [\#31](https://github.com/BoostV/process-optimizer-api/pull/31) ([langdal](https://github.com/langdal))

**Merged pull requests:**

- Build docker image for x86 and arm [\#32](https://github.com/BoostV/process-optimizer-api/pull/32) ([langdal](https://github.com/langdal))

## [v1.4.1](https://github.com/BoostV/process-optimizer-api/tree/v1.4.1) (2022-03-21)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v1.4.0...v1.4.1)

**Implemented enhancements:**

- Job queue for expensive calculations [\#29](https://github.com/BoostV/process-optimizer-api/issues/29)

**Fixed bugs:**

- Make sure matplot has a writable folder inside the docker container [\#3](https://github.com/BoostV/process-optimizer-api/issues/3)

**Closed issues:**

- Update to ProcessOptimizer 0.7.3 [\#28](https://github.com/BoostV/process-optimizer-api/issues/28)
- Issue with json objects [\#27](https://github.com/BoostV/process-optimizer-api/issues/27)

**Merged pull requests:**

- Feature/job queue [\#30](https://github.com/BoostV/process-optimizer-api/pull/30) ([langdal](https://github.com/langdal))

## [v1.4.0](https://github.com/BoostV/process-optimizer-api/tree/v1.4.0) (2021-09-23)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v1.3.0...v1.4.0)

**Implemented enhancements:**

- Add expected minimum to response [\#10](https://github.com/BoostV/process-optimizer-api/issues/10)

**Merged pull requests:**

- Expose expected minimum in result response [\#26](https://github.com/BoostV/process-optimizer-api/pull/26) ([langdal](https://github.com/langdal))
- Automatically generate changelog [\#25](https://github.com/BoostV/process-optimizer-api/pull/25) ([langdal](https://github.com/langdal))
- Rounding suggested experiment\(s\) to length scale of dimensions [\#21](https://github.com/BoostV/process-optimizer-api/pull/21) ([AkselObdrup](https://github.com/AkselObdrup))

## [v1.3.0](https://github.com/BoostV/process-optimizer-api/tree/v1.3.0) (2021-09-20)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v1.2.0...v1.3.0)

**Closed issues:**

- Axis labels cropped from plots [\#19](https://github.com/BoostV/process-optimizer-api/issues/19)
- Version information and detailed optimizer parameters should be part of the response [\#9](https://github.com/BoostV/process-optimizer-api/issues/9)

**Merged pull requests:**

- Bump urllib3 from 1.26.3 to 1.26.5 [\#24](https://github.com/BoostV/process-optimizer-api/pull/24) ([dependabot[bot]](https://github.com/apps/dependabot))
- Bump pillow from 8.1.0 to 8.3.2 [\#23](https://github.com/BoostV/process-optimizer-api/pull/23) ([dependabot[bot]](https://github.com/apps/dependabot))
- Feature/version information [\#22](https://github.com/BoostV/process-optimizer-api/pull/22) ([langdal](https://github.com/langdal))
- set bbox\_inches = 'tight' in savefig\(\) to avoid cropping [\#20](https://github.com/BoostV/process-optimizer-api/pull/20) ([AkselObdrup](https://github.com/AkselObdrup))
- Convert continuous and discrete values to float or int [\#18](https://github.com/BoostV/process-optimizer-api/pull/18) ([j-or](https://github.com/j-or))

## [v1.2.0](https://github.com/BoostV/process-optimizer-api/tree/v1.2.0) (2021-06-28)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v1.1.0...v1.2.0)

**Merged pull requests:**

- Request multiple experiments [\#17](https://github.com/BoostV/process-optimizer-api/pull/17) ([langdal](https://github.com/langdal))

## [v1.1.0](https://github.com/BoostV/process-optimizer-api/tree/v1.1.0) (2021-06-18)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v1.0.1...v1.1.0)

**Implemented enhancements:**

- Method for returning extra data to clients [\#13](https://github.com/BoostV/process-optimizer-api/issues/13)

**Fixed bugs:**

- Plots fail with UI thread error on MacOS [\#16](https://github.com/BoostV/process-optimizer-api/issues/16)

**Merged pull requests:**

- Add extras field to input specification [\#15](https://github.com/BoostV/process-optimizer-api/pull/15) ([langdal](https://github.com/langdal))

## [v1.0.1](https://github.com/BoostV/process-optimizer-api/tree/v1.0.1) (2021-06-17)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v1.0.0...v1.0.1)

**Merged pull requests:**

- Add extras to result [\#14](https://github.com/BoostV/process-optimizer-api/pull/14) ([langdal](https://github.com/langdal))

## [v1.0.0](https://github.com/BoostV/process-optimizer-api/tree/v1.0.0) (2021-05-11)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v0.0.2...v1.0.0)

**Implemented enhancements:**

- Return pickled result as part of response [\#6](https://github.com/BoostV/process-optimizer-api/issues/6)

**Merged pull requests:**

- Feature/\#6 pickle bundle [\#7](https://github.com/BoostV/process-optimizer-api/pull/7) ([langdal](https://github.com/langdal))

## [v0.0.2](https://github.com/BoostV/process-optimizer-api/tree/v0.0.2) (2021-04-19)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/v0.0.1...v0.0.2)

## [v0.0.1](https://github.com/BoostV/process-optimizer-api/tree/v0.0.1) (2021-04-19)

[Full Changelog](https://github.com/BoostV/process-optimizer-api/compare/6ed22c1622a302ab6ee66714cc1e40b334c43e16...v0.0.1)



\* *This Changelog was automatically generated by [github_changelog_generator](https://github.com/github-changelog-generator/github-changelog-generator)*
