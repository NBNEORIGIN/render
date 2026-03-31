"""SVG to PNG renderer using Playwright (headless Chromium).

Parallel implementation using a thread-pool where each worker owns its own
browser instance. This avoids cross-thread Playwright issues while allowing
multiple renders to run concurrently.
"""
import tempfile
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, Future
from playwright.sync_api import sync_playwright

# Each worker thread owns its own Playwright + browser instance
_thread_local = threading.local()
_WORKERS = 4
_executor = ThreadPoolExecutor(max_workers=_WORKERS, thread_name_prefix="playwright")


def _ensure_browser():
    """Get or create the browser for the current worker thread."""
    if not getattr(_thread_local, 'initialized', False):
        _thread_local.playwright = sync_playwright().start()
        _thread_local.browser = _thread_local.playwright.chromium.launch()
        _thread_local.initialized = True
    return _thread_local.browser


def _render_svg_impl(svg_content: str, scale: int, transparent: bool = False, full_page: bool = False) -> bytes:
    """Internal render function - runs on executor thread.
    
    Args:
        svg_content: SVG XML string
        scale: Device scale factor
        transparent: If True, omit background for transparency
        full_page: If True, capture full page bounds (for SVGs with elements outside viewBox)
    """
    browser = _ensure_browser()
    context = browser.new_context(device_scale_factor=scale)
    page = context.new_page()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False, encoding='utf-8') as f:
        f.write(svg_content)
        temp_svg = Path(f.name)
    
    try:
        # Reduced timeout from 60s to 30s for faster failure detection
        page.goto(f'file:///{temp_svg.as_posix()}', timeout=30000)
        page.wait_for_load_state('networkidle', timeout=5000)
        
        svg_element = page.locator('svg')
        
        if full_page:
            # For peel_and_stick: get the bounding box and set viewBox to capture all content
            # The peel_and_stick templates have content outside the original viewBox
            bbox = page.evaluate('''() => {
                const svg = document.querySelector('svg');
                const bbox = svg.getBBox();
                return {x: bbox.x, y: bbox.y, width: bbox.width, height: bbox.height};
            }''')
            
            if bbox and bbox['width'] > 0 and bbox['height'] > 0:
                # Update viewBox to include all content with small padding
                padding = 5
                new_viewbox = f"{bbox['x'] - padding} {bbox['y'] - padding} {bbox['width'] + padding * 2} {bbox['height'] + padding * 2}"
                # Calculate aspect ratio to set proper dimensions
                aspect = bbox['width'] / bbox['height'] if bbox['height'] > 0 else 1
                # Use a reasonable output size
                out_height = 800
                out_width = out_height * aspect
                page.evaluate(f'''() => {{
                    const svg = document.querySelector('svg');
                    svg.setAttribute('viewBox', '{new_viewbox}');
                    svg.removeAttribute('width');
                    svg.removeAttribute('height');
                    svg.style.width = '{out_width}px';
                    svg.style.height = '{out_height}px';
                }}''')
                # Re-locate after modification
                svg_element = page.locator('svg')
        
        # Reduced timeout from 60s to 30s
        png_bytes = svg_element.screenshot(type='png', omit_background=transparent, timeout=30000)
    finally:
        page.close()
        context.close()
        temp_svg.unlink(missing_ok=True)
    
    return png_bytes


def _render_svg_file_impl(svg_path: Path, scale: int) -> bytes:
    """Internal file render function - runs on executor thread."""
    browser = _ensure_browser()
    context = browser.new_context(device_scale_factor=scale)
    page = context.new_page()
    
    try:
        page.goto(f'file:///{svg_path.as_posix()}')
        svg_element = page.locator('svg')
        png_bytes = svg_element.screenshot(type='png')
    finally:
        page.close()
        context.close()
    
    return png_bytes


def _shutdown_thread_browser():
    """Close the browser owned by the current worker thread (called inside executor)."""
    if getattr(_thread_local, 'initialized', False):
        try:
            _thread_local.browser.close()
        except Exception:
            pass
        try:
            _thread_local.playwright.stop()
        except Exception:
            pass
        _thread_local.initialized = False


def close_browser():
    """Close all worker browsers and shutdown executor."""
    futures = [_executor.submit(_shutdown_thread_browser) for _ in range(_WORKERS)]
    for f in futures:
        try:
            f.result(timeout=10)
        except Exception:
            pass


def render_svg_to_png(svg_content: str, output_path: Path, scale: int = 4) -> Path:
    """
    Render SVG content to PNG using Playwright (thread-safe).
    
    Args:
        svg_content: SVG XML string
        output_path: Output PNG file path
        scale: Device scale factor (4 = ~2000px output for 500px SVG)
    
    Returns:
        Path to output PNG file
    """
    png_bytes = _executor.submit(_render_svg_impl, svg_content, scale).result(timeout=60)
    with open(output_path, 'wb') as f:
        f.write(png_bytes)
    return output_path


def render_svg_file_to_png(svg_path: Path, output_path: Path, scale: int = 4) -> Path:
    """
    Render SVG file to PNG using Playwright (thread-safe).
    
    Args:
        svg_path: Input SVG file path
        output_path: Output PNG file path
        scale: Device scale factor (4 = ~2000px output for 500px SVG)
    
    Returns:
        Path to output PNG file
    """
    png_bytes = _executor.submit(_render_svg_file_impl, svg_path, scale).result(timeout=60)
    with open(output_path, 'wb') as f:
        f.write(png_bytes)
    return output_path


def render_svg_to_bytes(svg_content: str, scale: int = 4, transparent: bool = False, full_page: bool = False) -> bytes:
    """
    Render SVG content to PNG bytes (thread-safe, for streaming/API responses).
    
    Args:
        svg_content: SVG XML string
        scale: Device scale factor
        transparent: If True, omit background for transparency
        full_page: If True, capture full page bounds (for SVGs with elements outside viewBox)
    
    Returns:
        PNG image as bytes
    """
    return _executor.submit(_render_svg_impl, svg_content, scale, transparent, full_page).result(timeout=60)


if __name__ == "__main__":
    # Test rendering
    test_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">
        <defs>
            <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="4" dy="4" stdDeviation="4" flood-opacity="0.5"/>
            </filter>
        </defs>
        <circle cx="100" cy="100" r="80" fill="#4CAF50" filter="url(#shadow)"/>
    </svg>"""
    
    output = Path("test_render.png")
    render_svg_to_png(test_svg, output)
    print(f"Rendered to {output} ({output.stat().st_size} bytes)")
    close_browser()
