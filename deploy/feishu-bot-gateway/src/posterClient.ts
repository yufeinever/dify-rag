export type PosterJob = {
  status: "queued" | "running" | "succeeded" | "failed";
  job_id: string;
  request_id: string;
  final_prompt: string;
  size: string;
  estimated_time_text?: string;
  poster_url?: string | null;
  thumbnail_url?: string | null;
  error?: string | null;
};

export class PosterClient {
  constructor(private readonly serviceUrl: string, private readonly size: string) {}

  async createJob(query: string, requestId: string): Promise<PosterJob> {
    const response = await fetch(`${this.serviceUrl.replace(/\/$/, "")}/v1/poster-jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        brief: {
          theme: query,
          background: query,
          audience: "飞书内部协作场景",
          brand_constraints: "参考 MMB 品牌资料和现有素材；不要生成不可证实的价格、承诺或水印。",
        },
        assets: [],
        size: this.size,
        overlay_text: false,
        request_id: requestId,
        user_query: query,
      }),
    });
    if (!response.ok) {
      throw new Error(`poster-service create job failed: ${response.status} ${await response.text()}`);
    }
    return response.json() as Promise<PosterJob>;
  }

  async getJob(jobId: string): Promise<PosterJob> {
    const response = await fetch(`${this.serviceUrl.replace(/\/$/, "")}/v1/poster-jobs/${encodeURIComponent(jobId)}`);
    if (!response.ok) {
      throw new Error(`poster-service get job failed: ${response.status} ${await response.text()}`);
    }
    return response.json() as Promise<PosterJob>;
  }
}
