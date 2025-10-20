import os

import environ


def loan_env(base_dir: str) -> environ.Env:
    env = environ.Env(DEBUG=(bool, False))
    env_file = os.path.join(base_dir, ".env")

    if os.path.isfile(env_file):
        env.read_env(env_file)
    else:
        raise Exception("No local .env detected. No secrets found.")

    return env
