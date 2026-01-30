# vagrant-spk

`vagrant-spk` is a tool designed to help app developers package apps for [Sandstorm](https://sandstorm.io).

## Example usage:

    git clone git://github.com/sandstorm-io/vagrant-spk
    git clone git://github.com/sandstorm-io/php-app-to-package-for-sandstorm
    export PATH=$(pwd)/vagrant-spk:$PATH
    cd php-app-to-package-for-sandstorm
    vagrant-spk setupvm lemp
    vagrant-spk vm up
    vagrant-spk init
    # edit .sandstorm/sandstorm-pkgdef.capnp in your editor of choice
    vagrant-spk dev
    # visit http://local.sandstorm.io:6090 in a web browser
    # log in as Alice, the admin account
    # launch an instance of the example app, play around with it
    # then, press Ctrl-C to stop the tracing vagrant-spk dev
    vagrant-spk pack example.spk
    # You now have an .spk file.  Yay!
    # Verify it works by going to http://local.sandstorm.io:6090,
    # select "My Files" -> "Upload an app", select your .spk file,
    # upload it, install it, and create a new instance of your app.

## What the files are for

`vagrant-spk` will create a `.sandstorm/` folder in your repo and set up some
files with some defaults for your app stack.  You will likely need to modify
some of these to adapt their behavior to make the most sense for your app.

See the [vagrant-spk docs on customizing your
package](https://docs.sandstorm.io/en/latest/vagrant-spk/customizing/)
for full details.

## Example apps

See the [example app listing in the vagrant-spk
documentation.](https://docs.sandstorm.io/en/latest/vagrant-spk/customizing/#example-setups)

## Running tests

The test suite uses [pytest](https://pytest.org/) and [uv](https://docs.astral.sh/uv/) for dependency management.

Run all tests:

    uv run pytest

Run tests with verbose output:

    uv run pytest -v

Run tests for a specific script:

    uv run pytest tests/test_lima_spk.py
    uv run pytest tests/test_vagrant_spk.py

Run shared tests that verify both scripts:

    uv run pytest tests/test_shared.py
