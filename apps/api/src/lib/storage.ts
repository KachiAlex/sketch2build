import { S3Client, PutObjectCommand, GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { v4 as uuidv4 } from "uuid";

const endpoint = process.env.S3_ENDPOINT;
const bucket = process.env.S3_BUCKET || "sketch2build";
const region = process.env.S3_REGION || "us-east-1";

function getEndpoint() {
  if (!endpoint) {
    throw new Error("S3_ENDPOINT environment variable is required");
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
        accessKeyId: process.env.S3_ACCESS_KEY || "sketch2build",
        secretAccessKey: process.env.S3_SECRET_KEY || "sketch2build",
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

  const url = await getSignedUrl(
    getS3Client(),
    new GetObjectCommand({ Bucket: bucket, Key: key }),
    { expiresIn: 3600 * 24 * 7 } // 7 days
  );

  return { key, url };
}
