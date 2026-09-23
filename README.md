# goodrun-backend
Backend for Good Run Project (updated for sprint 2)



# Notes

This requires [uv](https://docs.astral.sh/uv/) and Python 3.14, we should all use the same version of these for consistency. 

Run the following

```sh
make install
```
to install everything


then use
```sh 
make run
```
To actually run fast api, which should spawn the backend on `localhost:8000`


# Helpful Coding Practices

If your using VS CODE I highly reccomend that you install the Python extension. You can then click command shift p or ctrl shift p and 
type in 'interpreter' then hit enter on select python interpreter. select your interpreter. this will allow you to press comand (or contorl for windows) and click
on any class or function to automatically take you to the code that defines. its very helpful because we have quite a complicated / abstracted structure.


# General Commands to Run

`make format` formats and auto fixes linting issues
`make lint` checks formatting and liniting
`make typecheck` runs mypy to ensure all our types follow their definitions
`make test` runs test cases
`make check` runs all fo lint, typcheck and test. this is what you should run before pushing your PR.

# Repo Layout
```
app/
  main.py        FastAPI app
  api/           mounts every domain router under /api/v0
  auth/          each domain has its own package with a router
  orders/
  runs/
  volunteers/
  organisations/
  locations/
tests/
scripts/         CI helpers
```
