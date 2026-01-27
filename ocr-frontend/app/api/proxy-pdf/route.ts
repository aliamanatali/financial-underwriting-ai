import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const targetUrl = searchParams.get('url');

  if (!targetUrl) {
    return NextResponse.json({ error: 'Missing url parameter' }, { status: 400 });
  }

  try {
    const response = await fetch(targetUrl);

    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to fetch resource: ${response.status} ${response.statusText}` },
        { status: response.status }
      );
    }

    const contentType = response.headers.get('content-type') || 'application/pdf';
    const contentDisposition = response.headers.get('content-disposition');

    // Create a new response with the body from the fetch
    const newResponse = new NextResponse(response.body, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        // Forward Content-Disposition if it exists, otherwise standard inline for PDF
        ...(contentDisposition && { 'Content-Disposition': contentDisposition }),
        'Cache-Control': 'public, max-age=3600',
      },
    });

    return newResponse;
  } catch (error: any) {
    console.error('Proxy error:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}