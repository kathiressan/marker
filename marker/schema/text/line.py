import html
import re
from typing import Literal, List

import regex
import sys

from marker.schema import BlockTypes
from marker.schema.blocks import Block, BlockOutput

HYPHENS = r'-—¬'


def remove_tags(text):
    return re.sub(r'<[^>]+>', '', text)


def replace_last(string, old, new):
    matches = list(re.finditer(old, string))
    if not matches:
        return string
    last_match = matches[-1]
    return string[:last_match.start()] + new + string[last_match.end():]


def strip_trailing_hyphens(line_text, next_line_text, line_html) -> str:
    lowercase_letters = r'\p{Ll}'

    hyphen_regex = regex.compile(rf'.*[{HYPHENS}]\s?$', regex.DOTALL)
    next_line_starts_lowercase = regex.match(rf"^\s?[{lowercase_letters}]", next_line_text)

    if hyphen_regex.match(line_text) and next_line_starts_lowercase:
        line_html = replace_last(line_html, rf'[{HYPHENS}]', "")

    return line_html


class Line(Block):
    block_type: BlockTypes = BlockTypes.Line
    block_description: str = "A line of text."
    formats: List[Literal["math"]] | None = None # Sometimes we want to set math format at the line level, not span

    def formatted_text(self, document):
        text = ""
        for block in self.contained_blocks(document, (BlockTypes.Span,)):
            block_text = html.escape(block.text)

            if block.has_superscript:
                block_text = re.sub(r"^([0-9\W]+)(.*)", r"<sup>\1</sup>\2", block_text)
                if "<sup>" not in block_text:
                    block_text = f"<sup>{block_text}</sup>"

            if block.url:
                block_text = f"<a href='{block.url}'>{block_text}</a>"

            if block.italic:
                text += f"<i>{block_text}</i>"
            elif block.bold:
                text += f"<b>{block_text}</b>"
            elif block.math:
                text += f"<math display='inline'>{block_text}</math>"
            else:
                text += block_text

        return text

    def assemble_html(self, document, child_blocks, parent_structure):
        template = ""
        for c in child_blocks:
            template += c.html

        raw_text = remove_tags(template).strip()
        structure_idx = parent_structure.index(self.id)
        if structure_idx < len(parent_structure) - 1:
            next_block_id = parent_structure[structure_idx + 1]
            next_line = document.get_block(next_block_id)
            next_line_raw_text = next_line.raw_text(document)
            template = strip_trailing_hyphens(raw_text, next_line_raw_text, template)
        else:
            template = template.strip(' ')  # strip any trailing whitespace from the last line
        return template

    def render(self, document, parent_structure, section_hierarchy=None):
        child_content = []
        if self.structure is not None and len(self.structure) > 0:
            for block_id in self.structure:
                block = document.get_block(block_id)
                child_content.append(block.render(document, parent_structure, section_hierarchy))

        return BlockOutput(
            html=self.assemble_html(document, child_content, parent_structure),
            polygon=self.polygon,
            id=self.id,
            children=[],
            section_hierarchy=section_hierarchy
        )

    def merge(self, other):
        # Type checking
        if not isinstance(other, type(self)):
            raise TypeError(f"Cannot merge {type(self).__name__} with {type(other).__name__}")
        
        # Debug prints that write directly to stderr
        sys.stderr.write(f"Debug - Before checks: self.structure={self.structure}, other.structure={other.structure}\n")
        sys.stderr.flush()
        
        # Initialize structures defensively
        if self.structure is None:
            self.structure = []
        if not isinstance(self.structure, list):
            raise TypeError(f"self.structure must be list, got {type(self.structure)}")
        
        # Handle other.structure being None
        other_structure = [] if other.structure is None else other.structure
        if not isinstance(other_structure, list):
            raise TypeError(f"other.structure must be None or list, got {type(other.structure)}")
        
        sys.stderr.write(f"Debug - After initialization: self.structure={self.structure}, other_structure={other_structure}\n")
        sys.stderr.flush()
        
        self.polygon = self.polygon.merge([other.polygon])
        
        # Merge structures
        self.structure.extend(other_structure)  # Using extend instead of + for in-place modification
        
        if self.formats is None:
            self.formats = other.formats
        elif other.formats is not None:
            self.formats = list(set(self.formats + other.formats))
