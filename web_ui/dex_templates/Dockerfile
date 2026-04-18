# syntax=docker/dockerfile:1.7

###################
# dex_templates_source
###################
FROM scratch AS dex_templates_source

COPY --link static/    /dex_templates/static/
COPY --link templates/ /dex_templates/templates/
COPY --link themes/    /dex_templates/themes/
COPY --link robots.txt /dex_templates/robots.txt


###################
# dex_templates
###################
FROM debian:bookworm-slim@sha256:74d56e3931e0d5a1dd51f8c8a2466d21de84a271cd3b5a733b803aa91abf4421 AS dex_templates

COPY --link --from=dex_templates_source /dex_templates/ /dex_templates/
