import git
from pathlib import Path
import traceback
from flask import Flask
import toml
import logging
from time import sleep

config_path = Path.home() / '.sync-repo-service.toml'

if not config_path.exists():
    logging.warning("Config file not found, copied default config to ~/.sync-repo-service.toml")
    config_path = config_path.write_text((Path(__file__).parent / 'default_config.toml').read_text())

config = toml.load(config_path)

if config['use_webhook']:
    app = Flask(__name__)
    log = app.logger
else:
    log = logging.getLogger(__name__)

repo = git.Repo(Path(config['repo_path']).resolve())


def pull():
    log.debug("Pulling from remote...")
    origin = repo.remotes.origin
    origin.pull()
    repo.submodule_update(init=True, recursive=True)
    log.debug("Pull successful")

def check_if_changed():
    log.debug('Checking if repo has changed...')
    repo.remotes.origin.fetch()
    # TODO: I'm only sorta sure this is accurate, it needs to be tested
    local = repo.head.commit
    remote = repo.commit(f"origin/{repo.active_branch.name}")
    return local.hexsha != remote.hexsha

@app.post(config['webhook_path'])
def github_webhook():
    """ Triggered by the github repo. Pulls the latest changes and restarts the server """
    log.info("Github change detected")
    try:
        pull()
    except Exception as e:
        log.error("Failed to pull from remote: %s", e)
        return {"error": str(e), "traceback": traceback.format_exc()}, 500
    return {"status": "restarted"}, 200


if __name__ == "__main__":
    if config['use_webhook']:
        app.run(debug=False)
    else:
        while True:
            if check_if_changed():
                try:
                    pull()
                except Exception as e:
                    log.error("Failed to pull from remote: %s", e)
                    # log.error(traceback.format_exc())
            sleep(config['update_interval_seconds'])
