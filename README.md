# Dura Europos Wikidata Annotation

[This tool](https://dura-europos-wd-annotation.toolforge.org/) is a fork of [Wikidata Image Positions](https://wd-image-positions.toolforge.org/) meant for annotation of excavation photos of Dura-Europos. It includes (or will include soon) the original annotation features provided by Wikidata Image Positions along with a pre-queried dashboard of Dura-Europos related items, a streamlined annotating experience/tutorial, and approval system.

## Toolforge

On Wikimedia Toolforge, this tool runs under the `dura-europos-wd-annotation` tool name.
Source code resides in `~/www/python/src/`, a virtual environment is set up in `~/www/python/venv/`.

Start the webservice with
```
webservice --backend=kubernetes python3.11 start
```

To update the service, run the following commands after becoming the tool account:
```
cd ~/www/python/src
git fetch
git pull
webservice restart
```

If there were any changes in the Python environment (e.g. new dependencies),
add the following steps before the `webservice restart`:
```
webservice --backend=kubernetes python3.11 shell
source ~/www/python/venv/bin/activate
pip-sync ~/www/python/src/requirements.txt
```

## Local development setup

You can also run the tool locally:

```
git clone https://github.com/mary-jiang/dura-europos-wd-annotation
cd dura-europos-wd-annotation
pip3 install -r requirements.txt
FLASK_ENV=development flask run
```

You will have to set up your own config.yaml, [this tutorial is useful](https://wikitech.wikimedia.org/wiki/Help:Toolforge/My_first_Flask_OAuth_tool), and note that when logging in locally you may have to use the localhost version of the callback (take the oauth query out of the callback url and attach it to your localhost url, and you should be able to log in locally).

Some of the front-end components will not render correctly until you install the node modules. Just run `npm install` in the root directory to install these. You will have to install these in a node shell on the toolforge server by first running `webservice --backend=kubernetes node18 shell` before running the npm install.

This tool uses a sqlite database to keep data that is unique to this tool seperate from Wikidata databases (such as user permissions in the tool itself, local non-posted annotations). To generate a table from a template, run `python3 databasebuilder.py`.

## Contributing

Currently, this project is meant as a senior capstone project so I can obtain my bachelors degree. If you would like to contribute features that extend beyond the scope of Dura-Europos please consider contributing to the original project that this was forked from.

To send a patch, you can submit a
[pull request on GitHub](https://github.com/lucaswerkmeister/tool-wd-image-positions) or a
[merge request on GitLab](https://gitlab.wikimedia.org/toolforge-repos/wd-image-positions) to the original Wikidata Image Positions project.

## License

The code in this repository is released under the AGPL v3, as provided in the `LICENSE` file.
