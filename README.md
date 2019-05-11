# iamdb
[![Build Status](https://travis-ci.org/yehonatanz/iamdb.svg?branch=master)](https://travis-ci.org/yehonatanz/iamdb)
[![Maintainability](https://api.codeclimate.com/v1/badges/ca78817e0669a495bcf4/maintainability)](https://codeclimate.com/github/yehonatanz/iamdb/maintainability)
[![BCH compliance](https://bettercodehub.com/edge/badge/yehonatanz/iamdb?branch=master)](https://bettercodehub.com/)

Highly specific CLI tool to manage my watched movie statistics

Parse, enrich and store data about the movies I watched.

Powered by [click](https://palletsprojects.com/p/click), [click-config-file](https://github.com/phha/click_config_file), [IMDB](https://www.imdb.com/interfaces) and the fantastic [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).

Examples:
```bash
iamdb --help
iamdb sync
iamdb check
```

### TODO (unordered):
* Tests
* Search from CLI
* Integrate all of IMDB data, not just the basic CSV
* Predict what other movies I'd like
