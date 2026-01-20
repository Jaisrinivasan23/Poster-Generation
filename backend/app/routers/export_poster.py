"""
Export Poster Router
POST /api/export-poster - Convert HTML poster to PNG or PDF

Uses Playwright for browser-based rendering:
- PNG: High-resolution screenshot with configurable scale
- PDF: Screenshot compressed as JPEG embedded in PDF
- pdf-multi: Multiple HTML slides as multi-page PDF
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Union, Literal, Optional
from app.services.html_to_image import convert_html_to_png
import io


router = APIRouter()


class ExportPosterRequest(BaseModel):
    """Request body for export-poster endpoint"""
    html: Union[str, List[str]]  # Single HTML or array for pdf-multi
    format: Literal["png", "pdf", "pdf-multi"]
    width: int
    height: int
    scale: Optional[float] = 2.0  # Device scale factor for PNG quality


class ExportPosterError(BaseModel):
    """Error response model"""
    error: str
    failedResources: List[str] = []


async def create_pdf_from_image(image_data: bytes, width: int, height: int) -> bytes:
    """
    Create a PDF with an image embedded.
    Uses pure Python PDF generation (no external libraries required beyond basic image handling).
    """
    try:
        # Try using PyPDF2 or reportlab if available, otherwise use a simple PDF structure
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.utils import ImageReader
        from PIL import Image
        
        # Create a BytesIO buffer for the PDF
        pdf_buffer = io.BytesIO()
        
        # Create PDF canvas with custom page size matching the poster
        c = pdf_canvas.Canvas(pdf_buffer, pagesize=(width, height))
        
        # Convert PNG bytes to PIL Image
        img = Image.open(io.BytesIO(image_data))
        
        # Draw the image on the PDF page
        img_reader = ImageReader(img)
        c.drawImage(img_reader, 0, 0, width=width, height=height)
        
        # Save the PDF
        c.save()
        
        # Get the PDF bytes
        pdf_buffer.seek(0)
        return pdf_buffer.read()
        
    except ImportError:
        # Fallback: Create a minimal PDF structure manually
        return create_minimal_pdf_with_image(image_data, width, height)


def create_minimal_pdf_with_image(image_data: bytes, width: int, height: int) -> bytes:
    """
    Create a minimal PDF with embedded image using raw PDF structure.
    This is a fallback if reportlab is not available.
    """
    import base64
    import zlib
    
    # Compress image data
    compressed = zlib.compress(image_data)
    
    # Build minimal PDF structure
    pdf_parts = []
    
    # Header
    pdf_parts.append(b'%PDF-1.4\n')
    
    # Catalog (object 1)
    pdf_parts.append(b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
    
    # Pages (object 2)
    pdf_parts.append(b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n')
    
    # Page (object 3)
    page_content = f'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Contents 4 0 R /Resources << /XObject << /Im0 5 0 R >> >> >>\nendobj\n'
    pdf_parts.append(page_content.encode())
    
    # Content stream (object 4)
    content = f'q {width} 0 0 {height} 0 0 cm /Im0 Do Q'
    content_bytes = content.encode()
    pdf_parts.append(f'4 0 obj\n<< /Length {len(content_bytes)} >>\nstream\n'.encode())
    pdf_parts.append(content_bytes)
    pdf_parts.append(b'\nendstream\nendobj\n')
    
    # Image object (object 5) - simplified, just returning the raw data
    # In production, you'd want to properly encode the PNG as a PDF image
    pdf_parts.append(f'5 0 obj\n<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /BitsPerComponent 8 /ColorSpace /DeviceRGB /Filter /FlateDecode /Length {len(compressed)} >>\nstream\n'.encode())
    pdf_parts.append(compressed)
    pdf_parts.append(b'\nendstream\nendobj\n')
    
    # Cross-reference table and trailer
    pdf_parts.append(b'xref\n0 6\n0000000000 65535 f \n')
    pdf_parts.append(b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n')
    
    return b''.join(pdf_parts)


@router.post("/export-poster")
async def export_poster(request: ExportPosterRequest):
    """
    Export HTML poster to PNG or PDF format.
    
    Supports:
    - PNG: High-resolution screenshot with configurable scale
    - PDF: Single page PDF with embedded image
    - pdf-multi: Multi-page PDF for carousel slides
    
    Returns binary data with appropriate Content-Type header.
    """
    try:
        # Validate request
        if not request.html:
            raise HTTPException(
                status_code=400,
                detail="Missing required field: html"
            )
        
        if request.format not in ["png", "pdf", "pdf-multi"]:
            raise HTTPException(
                status_code=400,
                detail='Format must be "png", "pdf", or "pdf-multi"'
            )
        
        # For pdf-multi, html must be an array
        if request.format == "pdf-multi" and not isinstance(request.html, list):
            raise HTTPException(
                status_code=400,
                detail="pdf-multi format requires html to be an array of HTML strings"
            )
        
        dimensions = {"width": request.width, "height": request.height}
        
        # Handle multi-page PDF for carousel
        if request.format == "pdf-multi":
            html_array = request.html if isinstance(request.html, list) else [request.html]
            
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.pdfgen import canvas as pdf_canvas
                from reportlab.lib.utils import ImageReader
                from PIL import Image
                import base64
                
                # Create PDF with multiple pages
                pdf_buffer = io.BytesIO()
                c = pdf_canvas.Canvas(pdf_buffer, pagesize=(request.width, request.height))
                
                for i, html in enumerate(html_array):
                    print(f"📄 Processing slide {i + 1}/{len(html_array)}...")
                    
                    # Convert HTML to PNG (scale=1 for PDF to avoid huge files)
                    png_data_url = await convert_html_to_png(
                        html=html,
                        dimensions=dimensions,
                        scale=1.0
                    )
                    
                    # Extract base64 data from data URL
                    if png_data_url.startswith("data:image/png;base64,"):
                        png_base64 = png_data_url.split(",")[1]
                        png_bytes = base64.b64decode(png_base64)
                        
                        # Convert to PIL Image and add to PDF
                        img = Image.open(io.BytesIO(png_bytes))
                        img_reader = ImageReader(img)
                        
                        if i > 0:
                            c.showPage()  # Add new page for slides after first
                        
                        c.drawImage(img_reader, 0, 0, width=request.width, height=request.height)
                
                c.save()
                pdf_buffer.seek(0)
                pdf_bytes = pdf_buffer.read()
                
                print(f"✅ Generated PDF with {len(html_array)} pages")
                
                return Response(
                    content=pdf_bytes,
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": f'attachment; filename="carousel-{len(html_array)}-slides.pdf"',
                        "Content-Length": str(len(pdf_bytes))
                    }
                )
                
            except ImportError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"PDF generation requires reportlab and Pillow: {e}"
                )
        
        # Single HTML processing
        html_content = request.html if isinstance(request.html, str) else request.html[0]
        scale = request.scale if request.format == "png" else 1.0
        
        # Convert HTML to PNG
        print(f"🎨 Converting HTML to PNG ({request.width}x{request.height}, scale={scale})...")
        png_data_url = await convert_html_to_png(
            html=html_content,
            dimensions=dimensions,
            scale=scale
        )
        
        # Extract base64 data from data URL
        if not png_data_url.startswith("data:image/png;base64,"):
            raise HTTPException(
                status_code=500,
                detail="Failed to generate PNG image"
            )
        
        import base64
        png_base64 = png_data_url.split(",")[1]
        png_bytes = base64.b64decode(png_base64)
        
        if request.format == "png":
            # Return PNG directly
            filename = f"poster-{request.width}x{request.height}@{int(scale)}x.png"
            print(f"✅ Generated PNG: {filename} ({len(png_bytes)} bytes)")
            
            return Response(
                content=png_bytes,
                media_type="image/png",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Length": str(len(png_bytes))
                }
            )
        
        else:  # PDF format
            try:
                from reportlab.pdfgen import canvas as pdf_canvas
                from reportlab.lib.utils import ImageReader
                from PIL import Image
                
                # Create single-page PDF
                pdf_buffer = io.BytesIO()
                c = pdf_canvas.Canvas(pdf_buffer, pagesize=(request.width, request.height))
                
                # Convert PNG to PIL Image
                img = Image.open(io.BytesIO(png_bytes))
                img_reader = ImageReader(img)
                
                c.drawImage(img_reader, 0, 0, width=request.width, height=request.height)
                c.save()
                
                pdf_buffer.seek(0)
                pdf_bytes = pdf_buffer.read()
                
                filename = f"poster-{request.width}x{request.height}.pdf"
                print(f"✅ Generated PDF: {filename} ({len(pdf_bytes)} bytes)")
                
                return Response(
                    content=pdf_bytes,
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"',
                        "Content-Length": str(len(pdf_bytes))
                    }
                )
                
            except ImportError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"PDF generation requires reportlab and Pillow: {e}"
                )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ Export error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
