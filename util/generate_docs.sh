#!/bin/sh

set -e

VERSION=
ROOT_URL=
TEMP_DIR=
OUTPUT_DIR=

ShowUsage() {
    echo "Usage:"
    echo "    $PROG_NAME <options>"
    echo ""
    echo "    -v [version]"
    echo "    -r [root_url]"
    echo "    -t [tmp_dir]"
    echo "    -o [out_dir]"
    echo ""
}

while getopts "h?v:r:t:o:" opt; do
    case $opt in
        h|\?)
            ShowUsage
            exit 0
            ;;
        v)
            VERSION=$OPTARG
            ;;
        r)
            ROOT_URL=$OPTARG
            ;;
        t)
            TEMP_DIR=$OPTARG
            ;;
        o)
            OUTPUT_DIR=$OPTARG
            ;;
    esac
done

if [ "$VERSION" = "" ]; then
    echo "You need to specify a version number or label."
    exit 1
fi
if [ "$OUTPUT_DIR" = "" ]; then
    echo "You need to specify an output directory."
    exit 1
fi
if [ "$TEMP_DIR" = "" ]; then
    TEMP_DIR=_counter-docs
fi

echo "Updating virtual environment..."
venv/bin/pip install -r requirements.txt --upgrade

echo "Generate PieCrust version..."
venv/bin/python3 setup.py version

echo "Update Bower packages..."
bower update

echo "Baking documentation for version $VERSION..."
CHEF_ARGS="--root docs --config dist"
if [ ! "$ROOT_URL" = "" ]; then
    CHEF_ARGS="$CHEF_ARGS --config-set site/root $ROOT_URL"
fi
venv/bin/python3 chef.py $CHEF_ARGS bake -o $TEMP_DIR

echo "Synchronizing $OUTPUT_DIR"
if [ ! -d $OUTPUT_DIR ]; then
    mkdir -p $OUTPUT_DIR
fi
rsync -av --delete-after $TEMP_DIR/ $OUTPUT_DIR/

