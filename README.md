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


# Database

We use Postgres on [Neon](https://neon.com/). There is no local database and no JSON file
anymore, so you need a connection string before anything will start.

Make your own Neon branch rather than everyone sharing one, thats what branches are for and
it means you cant break someone elses data. Then put the connection string in a `.env` in
the project root:

```
DATABASE_URL=postgresql://user:pass@ep-xxx.aws.neon.tech/neondb?sslmode=require
```

`.env` is gitignored, keep it that way, it has the password in it.

Logins for the seeded accounts:

| email | password | role |
| --- | --- | --- |
| `admin` | `admin` | ADMIN |
| `tara@example.com` | `volunteer` | VOLUNTEER |
| `stores@rmh.example.com` | `organisation` | ORGANISATION |

NB: passwords are still plain text in the `password_hash` column. The column is named for
where this is going, hashing is a separate job.


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

NB: the tests need a seeded database to exist, but they dont create one. They assume the
fixtures from `seed.sql` are there (user 1 is the admin, order 2 is the available one, etc).
If they start failing in weird ways, re-run the seed script, your database has probably
drifted.

# Repo Layout
```
app/
  main.py        FastAPI app
  storage.py     the models, one per table in the data model
  queries.py     every SQL statement, plus the connection pool and the dependency
  schema.sql     the tables
  seed.sql       dev fixtures
  api/           mounts every domain router under /api/v0, plus shared auth dependencies
  auth/          each domain has its own package with a router and its schemas
  me/
  orders/
  runs/
  volunteers/
  organisations/
  locations/
tests/
scripts/         CI helpers, and db.py for applying the sql files
```

# How the database layer fits together

Routers never write SQL and never import psycopg. They ask for a `Queries` and call methods
on it:

```python
@router.get("/")
def get_volunteers(admin: AdminUser, queries: QueriesDep) -> VolunteersResponse:
    volunteers = queries.list_users_by_role(Role.VOLUNTEER)
```

`QueriesDep` tells FastAPI to run `get_queries()` before the endpoint and hand the result
in. That borrows one connection from the pool for the request and opens a transaction on
it, which commits if the endpoint returns normally and rolls back if it raises. So we never
write a commit anywhere, and a request that blows up half way through cant leave a half
finished run behind.

Its also the seam the tests use, `conftest` overrides `get_queries` with a transaction that
never commits, so every test is isolated without any cleanup code.
