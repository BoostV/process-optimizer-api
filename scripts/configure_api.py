import os
import pathlib
import yaml

from jinja2 import Environment

template = Environment()


def parse_yaml_config(config_path: pathlib.Path) -> dict:
    """
    load a yaml file, inject environment variables
    into it and return it as a dict
    """

    with open(config_path, encoding="utf-8", mode="r") as f:
        parsed_config = template.from_string(f.read()).render(**os.environ)
        return yaml.safe_load(parsed_config)


def write_yaml_config(config_dest: pathlib.Path, conf: dict) -> None:
    """write a jinja2 template to disk"""

    with open(config_dest, "w") as f:
        yaml.dump(conf, f, indent=2)


if __name__ == "__main__":
    # Open template
    source = pathlib.Path("templates/specification.yml.j2")
    conf = parse_yaml_config(config_path=source)
    print(f"loaded {source}", flush=True)

    # Write results
    destination = pathlib.Path("optimizerapi/openapi/specification.yml")
    write_yaml_config(config_dest=destination, conf=conf)
    print(f"wrote {destination}", flush=True)
