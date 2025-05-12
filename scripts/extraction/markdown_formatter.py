"""Module for formatting extracted content as markdown."""

import re
import os
from datetime import datetime
from google.genai import types  # Add this import
from ..config.extraction_prompt import get_extraction_prompt
from ..config import settings

class MarkdownFormatter:
    """Formats PDF content into structured markdown."""
    
    def __init__(self, pdf_reader):
        """Initialize with a PDFReader instance."""
        self.pdf_reader = pdf_reader
        
    def extract_metadata_from_path(self, pdf_path):
        """Extract metadata from PDF path components."""
        # Normalize path separators
        path = pdf_path.replace('\\', '/')
        
        # Extract components from path
        parts = path.split('/')
        filename = os.path.basename(pdf_path)
        filename_without_ext = os.path.splitext(filename)[0]
        
        # Extract course, module, and unit information
        course_id = None
        module_id = None
        unit_id = None
        
        for part in parts:
            if part.startswith('CON'):
                course_id = part.split('-')[0]
            elif part.startswith('MOD'):
                module_id = part.split('-')[0]
            elif part.startswith('UNI'):
                unit_id = part.split('-')[0] if '-' in part else part.split('_')[0]
        
        # If unit_id wasn't found in the path, extract from filename
        if not unit_id and filename_without_ext.startswith('UNI'):
            unit_id = filename_without_ext.split('-')[0] if '-' in filename_without_ext else filename_without_ext.split('_')[0]
        
        # Extract unit_title_id from filename (removing .pdf extension and UNI prefix)
        unit_title_id = filename_without_ext
        if unit_title_id.startswith('UNI'):
            # Remove the UNI#### prefix if present
            unit_title_id = '_'.join(unit_title_id.split('_')[1:])
        
        # Extract phase (AS, IGCSE, etc.)
        phase = None
        for phase_option in ['AS', 'IGCSE', 'A2']:
            if phase_option.lower() in pdf_path.lower():
                phase = phase_option
                break
        
        return {
            'unit_id': unit_id or 'UNI0001',  # Fallback if extraction failed
            'unit_title_id': unit_title_id or os.path.splitext(filename)[0],
            'parent_module_id': module_id or 'MOD0001',
            'parent_course_id': course_id or 'COU0001',
            'phase': phase or 'Unknown',
            'batch_id': 'BAT0001',  # Default batch ID
            'extraction_date': datetime.now().strftime('%Y-%m-%d')
        }
    
    def extract_and_format(self, pdf_info, metadata=None):
        """Extract content from PDF and format as markdown."""
        # If metadata not provided, try to extract from path
        if not metadata and 'path' in pdf_info:
            metadata = self.extract_metadata_from_path(pdf_info['path'])
        
        # Prepare the extraction prompt with metadata
        prompt = get_extraction_prompt(metadata)
        
        # Send to Gemini for extraction
        try:
            if pdf_info['method'] == 'direct':
                # For direct method (files under 20MB)
                response = self.pdf_reader.client.models.generate_content(
                    model=self.pdf_reader.model_id,
                    contents=[
                        types.Part.from_bytes(
                            data=pdf_info['data'],
                            mime_type='application/pdf',
                        ),
                        prompt
                    ]
                )
            else:
                # For File API method (files over 20MB)
                file_obj = self.pdf_reader.client.files.upload(
                    file=pdf_info['path'],
                    config=dict(mime_type='application/pdf')
                )
                
                response = self.pdf_reader.client.models.generate_content(
                    model=self.pdf_reader.model_id,
                    contents=[file_obj, prompt]
                )
            
            # Get the markdown content from the response
            markdown_content = response.text
            
            # Post-process the markdown content
            processed_content = self.post_process_markdown(markdown_content, metadata)
            
            return {
                'success': True,
                'content': processed_content,
                'metadata': metadata
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'metadata': metadata
            }
    
    def post_process_markdown(self, content, metadata):
        """Apply post-processing to the generated markdown."""
        # Check if content has frontmatter, if not add it
        if not content.startswith('---'):
            frontmatter = self.generate_frontmatter(metadata)
            content = frontmatter + '\n\n' + content
        
        # Ensure all section markers are present
        required_sections = [
            'INTRODUCTION',
            'LEARNING-OBJECTIVES',
            'MAIN-CONTENT-AREA',
            'KEY-TAKEAWAYS'
        ]
        
        for section in required_sections:
            section_marker = f"<!-- SECTION: {section} -->"
            if section_marker not in content:
                # Add missing section markers where they most likely belong
                if section == 'INTRODUCTION' and '# ' in content:
                    # Add after the first heading
                    content = re.sub(r'(# .+?\n)', r'\1\n' + section_marker + '\n', content, count=1)
                elif section == 'LEARNING-OBJECTIVES' and '## Learning Objectives' in content:
                    # Add before the learning objectives heading
                    content = content.replace('## Learning Objectives', section_marker + '\n## Learning Objectives')
                elif section == 'MAIN-CONTENT-AREA' and '## ' in content:
                    # Add before the first content section (second-level heading)
                    second_heading_match = re.search(r'## (?!Learning Objectives|Introduction).+?\n', content)
                    if second_heading_match:
                        pos = second_heading_match.start()
                        content = content[:pos] + section_marker + '\n\n' + content[pos:]
                elif section == 'KEY-TAKEAWAYS' and '## ' in content:
                    # Add towards the end, before any references
                    if '## References' in content:
                        content = content.replace('## References', section_marker + '\n\n## Key Takeaways\n\n## References')
                    else:
                        content += f"\n\n{section_marker}\n\n## Key Takeaways\n\n"
        
        # Fix image references
        img_assets_dir = f"./{metadata['unit_title_id']}-img-assets"
        content = re.sub(
            r'!\[(.*?)\]\((.*?)(?:\.(?:png|jpg|jpeg|gif))\)',
            r'![\1](' + img_assets_dir + r'/fig1-image.png)',
            content
        )
        
        # Ensure proper spacing around section markers
        content = re.sub(r'(\n*)(<!--.*?-->)(\n*)', r'\n\n\2\n\n', content)
        
        # Clean up excess whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content
    
    def generate_frontmatter(self, metadata):
        """Generate YAML frontmatter from metadata."""
        return f"""---
unit-id: {metadata.get('unit_id', 'UNI0001')}
unit-title-id: {metadata.get('unit_title_id', 'unknown')}
unit-title: {metadata.get('unit_title', 'Unknown Title')}
phase: {metadata.get('phase', 'Unknown')}
subject: {metadata.get('subject', 'Unknown')}
parent-module-id: {metadata.get('parent_module_id', 'MOD0001')}
parent-course-id: {metadata.get('parent_course_id', 'COU0001')}
batch-id: {metadata.get('batch_id', 'BAT0001')}
extraction-date: {metadata.get('extraction_date', datetime.now().strftime('%Y-%m-%d'))}
extractor-name: "Automated Extraction"
---"""