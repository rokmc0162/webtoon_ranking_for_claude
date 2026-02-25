import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/supabase";
import https from "https";
import http from "http";

function downloadImage(url: string): Promise<{ buffer: Buffer; contentType: string }> {
  return new Promise((resolve, reject) => {
    const client = url.startsWith("https") ? https : http;
    const req = client.get(
      url,
      {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
          Accept: "image/*,*/*",
        },
        timeout: 15000,
      },
      (res) => {
        // Handle redirects
        if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          downloadImage(res.headers.location).then(resolve).catch(reject);
          return;
        }

        if (res.statusCode !== 200) {
          reject(new Error(`HTTP ${res.statusCode}`));
          return;
        }

        const chunks: Buffer[] = [];
        res.on("data", (chunk: Buffer) => chunks.push(chunk));
        res.on("end", () => {
          const buffer = Buffer.concat(chunks);
          // content-type이 image가 아니면 image/jpeg로 강제
          let contentType = res.headers["content-type"] || "image/jpeg";
          if (!contentType.startsWith("image/")) {
            contentType = "image/jpeg";
          }
          resolve({ buffer, contentType });
        });
        res.on("error", reject);
      }
    );
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("timeout"));
    });
  });
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const platform = searchParams.get("platform") || "";
  const title = searchParams.get("title") || "";

  if (!platform || !title) {
    return NextResponse.json({ error: "platform and title required" }, { status: 400 });
  }

  // DB에서 base64 우선, 없으면 URL 가져오기 (잘린 제목 prefix 매칭 폴백)
  let rows = await sql`
    SELECT thumbnail_base64, thumbnail_url
    FROM works
    WHERE platform = ${platform} AND title = ${title}
    LIMIT 1
  `;

  // 정확히 안 맞으면 prefix 매칭 시도 (Asura 잘린 제목 대응)
  if (rows.length === 0 && title.length >= 10) {
    rows = await sql`
      SELECT thumbnail_base64, thumbnail_url
      FROM works
      WHERE platform = ${platform} AND title LIKE ${title + '%'}
      LIMIT 1
    `;
  }

  if (rows.length === 0) {
    return new NextResponse(null, { status: 404 });
  }

  const { thumbnail_base64, thumbnail_url } = rows[0];

  // base64가 있으면 그대로 반환
  if (thumbnail_base64) {
    const match = thumbnail_base64.match(/^data:([^;]+);base64,(.+)$/);
    if (match) {
      const mimeType = match[1];
      const base64Data = match[2];
      const buffer = Buffer.from(base64Data, "base64");
      return new NextResponse(new Uint8Array(buffer), {
        headers: {
          "Content-Type": mimeType,
          "Cache-Control": "public, max-age=86400",
        },
      });
    }
  }

  // URL이 있으면 Node.js http/https로 직접 다운로드
  if (thumbnail_url) {
    try {
      const { buffer, contentType } = await downloadImage(thumbnail_url);
      return new NextResponse(new Uint8Array(buffer), {
        headers: {
          "Content-Type": contentType,
          "Cache-Control": "public, max-age=86400",
          "Access-Control-Allow-Origin": "*",
        },
      });
    } catch {
      return new NextResponse(null, { status: 502 });
    }
  }

  return new NextResponse(null, { status: 404 });
}
