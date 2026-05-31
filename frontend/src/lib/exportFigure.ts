/**
 * Client-side figure export. ECharts renders SVG, so we serialize the rendered
 * `<svg>` directly — vector for publication, or rasterized to PNG.
 */

function triggerDownload(href: string, filename: string): void {
  const a = document.createElement('a');
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function serialize(svg: SVGSVGElement): { data: string; width: number; height: number } {
  const rect = svg.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width || svg.viewBox.baseVal.width || 640));
  const height = Math.max(1, Math.round(rect.height || svg.viewBox.baseVal.height || 400));
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clone.setAttribute('width', String(width));
  clone.setAttribute('height', String(height));
  return { data: new XMLSerializer().serializeToString(clone), width, height };
}

export function downloadSvg(svg: SVGSVGElement, name: string): void {
  const { data } = serialize(svg);
  const blob = new Blob([data], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  triggerDownload(url, `${name}.svg`);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function downloadPng(svg: SVGSVGElement, name: string, scale = 2): Promise<void> {
  const { data, width, height } = serialize(svg);
  const blob = new Blob([data], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  try {
    const img = new Image();
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error('svg render failed'));
      img.src = url;
    });
    const canvas = document.createElement('canvas');
    canvas.width = width * scale;
    canvas.height = height * scale;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#070a0f';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    triggerDownload(canvas.toDataURL('image/png'), `${name}.png`);
  } finally {
    URL.revokeObjectURL(url);
  }
}
