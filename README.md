# PieCrust

## Basic Configuration

PieCrust comes with a simple way to work with the 90% case: a personal website with a blog. You don't have anything to define, but you can customize some aspects of that default setup. From most likely to less likely:

* changing the URL format of posts
* changing the URL format of tags/categories
* defining new taxonomies (by default PieCrust comes with tags and categories)
* adding secondary blogs

## Advanced Configuration

PieCrust defines content using 3 concepts: *sources*, *taxonomies*, and *routes*.

### Sources

Sources define where your content is on disk, and how it's organized. By default, a source will use the `simple` scanner, but you can use other scanners that can can look for files differently, or can lift metadata information from the file names. For example, the `ordered` scanner will return the page files in the order defined by their file name prefix, and the `posts` collection of scanners will associate a date to each page based on their file name.

	sources:
		posts:
			type: posts/flat
		recipes
		reviews:
			type: ordered

### Taxonomies

Taxonomies are used by PieCrust to generate listings of pages based on the metadata they have. For instance, you usually want pages listing posts for each existing tag.

	taxonomies:
		tags:
			multiple: true
		category
		course
		ingredients:
			multiple: true

### Routes

Routes define the shape of the URLs used to access your content. URLs for the built-in `pages` source cannot be changed, but you can specify URL routes for all custom sources and taxonomies.

	routes:
		/%year%/%month%/%slug%:
			source: posts
		/recipes/%slug%:
			source: recipes
		/recipes/tag/%value%:
			source: recipes
			taxonomy: tags
		/recipes/ingredient/%value%:
			source: recipes
			taxonomy: ingredients
		/reviews/%slug%:
			source: reviews
