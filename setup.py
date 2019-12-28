import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="django_nplusone",
    version="0.0.3",
    author="Shafiq Ur Rahman",
    author_email="shafiq.tnoli@gmail.com",
    description="Discover possible N+1 queries in your code base",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/shaffooo/django_nplusone",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 2",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
    ],
    install_requires=[
          'Django>=1.11.20',
    ],
    python_requires='>=2.7',
)
