import { S3Client, PutObjectCommand, GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { v4 as uuidv4 } from "uuid";

const endpoint = process.env.S3_ENDPOINT || process.env.R2_ENDPOINT;
const bucket = process.env.S3_BUCKET || process.env.R2_BUCKET || "sketch2build";
const region = process.env.S3_REGION || "auto";
const r2PublicUrl = process.env.R2_PUBLIC_URL;

function getEndpoint() {
  if (!endpoint) {
    throw new Error("S3_ENDPOINT or R2_ENDPOINT environment variable is required");
  }
  return endpoint;
}

let _s3Client: S3Client | null = null;

export function getS3Client(): S3Client {
  if (!_s3Client) {
    _s3Client = new S3Client({
      endpoint: getEndpoint(),
      region,
      credentials: {
        accessKeyId: process.env.S3_ACCESS_KEY || process.env.R2_ACCESS_KEY_ID || "",
        secretAccessKey: process.env.S3_SECRET_KEY || process.env.R2_SECRET_ACCESS_KEY || "",
      },
      forcePathStyle: true,
    });
  }
  return _s3Client;
}

export async function uploadFile(
  fileBuffer: Buffer,
  contentType: string,
  extension: string,
  prefix = "uploads"
): Promise<{ key: string; url: string }> {
  const key = `${prefix}/${uuidv4()}.${extension}`;

  await getS3Client().send(
    new PutObjectCommand({
      Bucket: bucket,
      Key: key,
      Body: fileBuffer,
      ContentType: contentType,
    })
  );

  if (r2PublicUrl) {
    const publicUrl = r2PublicUrl.replace(/\/$/, "") + "/" + key;
    return { key, url: publicUrl };
  }

  const url = await getSignedUrl(
    getS3Client(),
    new GetObjectCommand({ Bucket: bucket, Key: key }),
    { expiresIn: 3600 * 24 * 7 } // 7 days
  );

  return { key, url };
}
