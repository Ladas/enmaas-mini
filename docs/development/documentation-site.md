# Documentation site

Documentation is staged into `.docs-build` and rendered with MkDocs Material.

```console
scripts/docs/serve build
scripts/docs/serve
```

GitHub Pages deploys from `main` with
[pages.yml](https://github.com/redhat-et/enmaas-mini/blob/main/.github/workflows/pages.yml).
Pull requests run the same strict build but do not publish.
