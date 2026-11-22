# Recipes

A collection of recipes in markdown. Published on Github pages at https://idcrosby.github.io/recipes/

## Import a recipe from a URL

1. Open [Import recipe from URL](https://github.com/idcrosby/recipes/actions/workflows/import-recipe.yml) in GitHub Actions.
2. Choose **Run workflow**, paste a public HTTPS recipe link, and select a cookbook category.
3. Open the finished run and follow the review link in its summary. Check the ingredients and instructions against the original recipe, then merge the pull request when it is ready to publish.

The importer reads structured recipe data embedded in the source page. Some sites omit that data or block automated requests. If the import fails, try another source or add the Markdown by hand.

For automatic draft pull requests, enable **Allow GitHub Actions to create and approve pull requests** in the repository’s **Settings → Actions → General**. If this is disabled, the workflow saves the recipe on a branch and provides a link to open the pull request yourself.

To import into a local checkout, run `python3 scripts/import_recipe.py --category Baking https://example.com/recipe`. The command creates a file in `docs/_recipes/` for review.
