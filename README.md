# django_nplusone
Discover possible N+1 queries in Django ORM at runtime

The objective of this library is to help you discover any N+1s in your code at development time.  

## Installation

Install the package from PyPI using `pip` as following

```
pip install django_nplusone
```

## Usage

Once package is installed, you can register the package in your `settings.py` as:

```
import nplusone

if DEBUG:
    nplusone.show_nplusones()

```

This should start logging possible N+1s warnings using your logger configuration. The library uses standard python `logging` module and uses logger by the name of `nplusone`.

