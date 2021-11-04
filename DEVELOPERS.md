# Developer documentation

- [Local development](#local-development)
  - [Native](#native)
    - [Prerequisites](#prerequisites)
    - [Steps](#steps)
  - [Docker Compose](#docker-compose)
  - [Frontend development (CSS/JS)](#frontend-development-cssjs)
  - [Running the local asset server](#running-the-local-asset-server)
  - [Compiling assets](#compiling-assets)
- [Deployment](#deployment)
- [Testing](#testing)
- [Adding new backends](#adding-new-backends)
  - [Steps to add a backend](#steps-to-add-a-backend)
  - [Why add a backend?](#why-add-a-backend)

## Local development

### Development credentials

_Note:_ you will need the [Bitwarden CLI tool](https://bitwarden.com/help/article/cli/) installed in order to access passwords, but it is not a requirement.
- There is an existing `dotenv-sample` template that you can use to base
  your own `.env` file on.
- Use `bw` to login to the Bitwarden account.
- When logged in to Bitwarden, run `scripts/dev-env.sh
  <env_file_target>` to retrieve and write the credentials to the target
  environment file specified.
  - `.env` is already in `.gitignore` to help prevent an accidental
    commit of credentials.

### Native

#### Prerequisites

- **Python v3.9.x**
- **virtualenv**
- **Pip**
- **Node.js v16.x** ([fnm](https://github.com/Schniz/fnm#installation) is recommended)
- **npm v7.x**

#### `just` commands

Each `just` command sets up a dev environment as part of running it.
If you want to maintain your own virtualenv make sure you have activated it before running a `just` command and it will be used instead.

#### Steps


**Set up an environment**

```sh
just devenv
```

**Run migrations:**

```sh
python manage.py migrate
```

Optionally set up 1 or more administrators by setting `ADMIN_USERS` to a list of strings.
For example: `ADMIN_USERS=ghickman,ingelsp`.

_Note:_ this can only contain usernames which exist in the database.
If necessary, you can create the required user(s) first with:

```sh
python manage.py createsuperuser
```

Then update their User records with:

```sh
python manage.py ensure_admins
```

**Build the assets:**

```sh
npm run build
```

**Run the dev server:**

```sh
just run
```

Access at [localhost:8000](http://localhost:8000)

### Docker Compose

Run `docker-compose up`.

_Note:_ The dev server inside the container does not currently reload when changes are saved.

### Frontend development (CSS/JS)

This project uses [Vite](https://vitejs.dev/), a modern build tool and development server, to build the frontend assets.
Vite integrates into the Django project using the [django-vite](https://github.com/MrBin99/django-vite) package.

Vite works by compiling JavaScript files, and outputs a manifest file, the JavaScript files, and any included assets such as stylesheets or images.

Vite adds all JavaScript files to the page using [ES6 Module syntax](https://caniuse.com/es6-module).
For legacy browsers, this project is utilising the [Vite Legacy Plugin](https://github.com/vitejs/vite/tree/main/packages/plugin-legacy) to provide a fallback using the [module/nomodule pattern](https://philipwalton.com/articles/deploying-es2015-code-in-production-today/).

For styling this project uses [Scss](https://www.npmjs.com/package/sass) to compile the stylesheets, and then [PostCSS](https://github.com/postcss/postcss) for post-processing.

### Running the local asset server

Vite has a built-in development server which will serve the assets and reload them on save.

To run the development server:

1. Update the `.env` file to `DJANGO_VITE_DEV_MODE=True`
2. Open a new terminal and run `npm run dev`

This will start the Vite dev server at [localhost:3000](http://localhost:3000/) and inject the relevant scripts into the Django templates.

### Compiling assets

To view the compiled assets:

1. Update the `.env` file to `DJANGO_VITE_DEV_MODE=False`
2. Run `npm run build`
3. Run `python manage.py collectstatic`

Vite builds the assets and outputs them to the `assets/dist` folder.

[Django Staticfiles app](https://docs.djangoproject.com/en/3.2/ref/contrib/staticfiles/) then collects the files and places them in the `staticfiles/assets` folder, with the manifest file located at `staticfiles/manifest.json`.

## Deployment

It is currently configured to be deployed Heroku-style, and requires the environment variables defined in `dotenv-sample`.

The DataLab job server is deployed to our `dokku2` instance, instructions are are in [INSTALL.md](INSTALL.md).

## Testing

Run the tests with:

```sh
just test
```

More details on testing can be found in [TESTING.md](TESTING.md).

## Backends

Backends in this project represent a [job runner](https://github.com/opensafely-core/job-runner) instance somewhere.
They are a Django model with a unique authentication token attached.

This has allowed us some benefits:

- API requests can be tied directly to a Backend (eg get all JobRequests for TPP).
- Per-Backend API stats collection is trivial because requests are tied to a Backend via auth.
