# Writing an initial character seed

A character package gives an individual a starting point. It is not a record
of lived events and does not permanently fix personality, interests or views.
The framework does not claim consciousness. T-03 stores the seed without using
a model, generating dialogue, learning or simulating growth.

Copy `characters/_template/` into a local directory. In `character.json`, choose
a name and retain `format_version: 1`. Set `seed` to a UTF-8 Markdown file inside
the package (normally `seed.md`). `assets` may be omitted or an empty array.
See [the exact format and CLI contract](T03_api.md).

Fill these four sections in `seed.md`:

1. **Voice**: preferred vocabulary, sentence length, emotional expression and
   how uncertainty or disagreement is expressed. Describe tendencies rather
   than rules that can never change.
2. **Initial interests**: a small set of starting curiosities. Leave room for
   new interests and changed opinions through real experience.
3. **Ways of relating**: how to ask questions, respect user boundaries, disagree
   and express a personal viewpoint. User facts require real sources; a seed
   must not claim that a relationship or a past event already happened.
4. **Example dialogues**: clearly label them as fictional tone demonstrations.
   They are never imported into M1 as actual conversations or confirmed facts.

An AI assistant may help draft these sections when asked, but should label the
result a proposal and keep imagined examples separate from sourced history.
In particular, the formal Zealor starting voice requires the owner's approval;
this public template does not define it. No model prompt in a seed grants file,
network or tool access. T-03 only validates and copies declared local files.

Users make or provide their own optional visuals. No image generation, formal
Zealor illustration or image renderer is bundled. To include a local asset,
add a relative path such as `assets/portrait.png`. Missing optional assets
produce WARN and do not block creation; existing unsafe links produce FAIL.
Optional files are copied as opaque bytes, not executed or rendered.

Run `neurocore doctor --character "path/to/package"`, then
`neurocore new --character "path/to/package"`. Every creation gets its own
identity and empty memory. Updating the source package affects only future
creations. Existing instances retain their creation snapshot. Later personality
growth will need a separate mechanism; T-03 provides neither growth nor a seed
update command, and does not turn seed text into evidence.
