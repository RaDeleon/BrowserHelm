"""Validate a release tag against the source version without starting the app."""
import argparse
import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def build_metadata(path=ROOT / 'neo-personal/version.py'):
    values = {}
    for node in ast.parse(pathlib.Path(path).read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('VERSION', 'BUILD'):
                    values[target.id] = ast.literal_eval(node.value)
    if not isinstance(values.get('VERSION'), str) or not re.fullmatch(r'\d+\.\d+\.\d+', values['VERSION']):
        raise ValueError('Expected a three-part app version')
    if not isinstance(values.get('BUILD'), str) or not re.fullmatch(r'[1-9]\d*', values['BUILD']):
        raise ValueError('Expected a positive bundle build number')
    return values


def validate_tag(tag, version):
    if tag != 'v' + version:
        raise ValueError('Release tag must match the app version: v' + version)
    return tag


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag')
    args = parser.parse_args()
    version = build_metadata()['VERSION']
    validate_tag(args.tag, version)
    notes = ROOT / 'docs/release-notes' / (version + '.md')
    if not notes.is_file():
        raise ValueError('Add release notes at ' + str(notes.relative_to(ROOT)))
    print('Validated ' + args.tag)


if __name__ == '__main__':
    main()
