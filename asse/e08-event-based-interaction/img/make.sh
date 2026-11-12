#!/bin/sh
# Render the rule diagrams of the deck to SVG (needs plantuml).
# PlantUML measures text with the font "sans-serif" and fixes each label's width;
# the slides should show Gill Sans where it is installed, so swap in a font list.
set -e
cd "$(dirname "$0")"
plantuml -tsvg rules-*.puml
sed -i "s/font-family=\"sans-serif\"/font-family=\"'Gill Sans Nova','Gill Sans MT Pro','Gill Sans',sans-serif\"/g" rules-*.svg
# PlantUML draws the small component icon with the box's border style; keep icons thin and solid.
sed -i -E 's/(<rect [^>]*width="(15|4)" [^>]*stroke-width:)2\.5;stroke-dasharray:7,7;/\10.5;/g' rules-*.svg
# The event-interaction graph from the Assignment 7 deck (TikZ; needs xelatex and pdftocairo).
tmp=$(mktemp -d)
xelatex -interaction=nonstopmode -halt-on-error -output-directory="$tmp" event-interactions.tex >/dev/null
pdftocairo -svg "$tmp/event-interactions.pdf" event-interactions.svg
rm -rf "$tmp"
