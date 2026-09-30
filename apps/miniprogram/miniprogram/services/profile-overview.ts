export interface TargetProfileOverview {
  id: string
  target_role: string
  relevant_experience_months: number
}

export interface CurrentResumeOverview {
  id: string
  original_file_name: string
  media_type: string
  size_bytes: number
  revision: number
  uploaded_at: string
  updated_at: string
}

export interface ProfileOverview {
  id: string
  nickname: string
  avatar_url: string | null
  avatar_url_expires_at: string | null
  default_target_profile: TargetProfileOverview | null
  current_resume: CurrentResumeOverview | null
  recent_scores: unknown[]
}

interface RequestResponse {
  statusCode: number
  data: unknown
}

interface RequestOptions {
  url: string
  method: "GET"
  success: (response: RequestResponse) => void
  fail: () => void
}

export type ProfileOverviewRequest = (options: RequestOptions) => void

export type ProfileOverviewRequestErrorCode = "http_error" | "network_error"

export class ProfileOverviewRequestError extends Error {
  readonly code: ProfileOverviewRequestErrorCode

  constructor(code: ProfileOverviewRequestErrorCode) {
    super(code === "network_error" ? "Unable to reach the API." : "The API request failed.")
    this.name = "ProfileOverviewRequestError"
    this.code = code
  }
}

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8080"

export function fetchProfileOverview(
  request: ProfileOverviewRequest = requestWithWechat,
  apiBaseUrl = DEFAULT_API_BASE_URL,
): Promise<ProfileOverview> {
  return new Promise((resolve, reject) => {
    request({
      url: `${apiBaseUrl}/api/v1/me/overview`,
      method: "GET",
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data as ProfileOverview)
          return
        }
        reject(new ProfileOverviewRequestError("http_error"))
      },
      fail() {
        reject(new ProfileOverviewRequestError("network_error"))
      },
    })
  })
}

const requestWithWechat: ProfileOverviewRequest = (options) => {
  wx.request({
    url: options.url,
    method: options.method,
    success(response) {
      options.success({
        statusCode: response.statusCode,
        data: response.data,
      })
    },
    fail() {
      options.fail()
    },
  })
}
