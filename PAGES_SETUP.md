# GitHub Pages Setup

If the deployed site is a white page, GitHub Pages is probably serving the source repository instead of the built PWA.

Use this setting in GitHub:

1. Open the repository on GitHub.
2. Go to **Settings**.
3. Open **Pages**.
4. Under **Build and deployment**, set **Source** to **GitHub Actions**.
5. Save, then run the `Deploy PWA to GitHub Pages` workflow again or push a new commit.

The working PWA URL should be:

```text
https://sourmilkman.github.io/AI-image-search/
```

Do not use **Deploy from a branch / main / root** for this project. That serves the development `index.html`, which references `src/main.tsx` and will render as a blank page on GitHub Pages.
