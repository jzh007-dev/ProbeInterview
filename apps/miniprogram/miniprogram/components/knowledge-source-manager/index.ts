import {
  fetchKnowledgeSources,
  KnowledgeSourceApiError,
  type KnowledgeSourceCollection,
  type KnowledgeSourceItem,
  type KnowledgeSourceQuota,
  type KnowledgeSourceScope,
  uploadKnowledgeSource,
} from "../../services/knowledge-sources"
import {
  createIdempotencyKey,
  formatFileSize,
  formatUploadTime,
  quotaExhausted,
  sortNewestFirst,
} from "../../utils/knowledge-sources"

interface SelectedFile {
  name: string
  path: string
  size: number
  sizeLabel: string
}

interface DisplayItem extends KnowledgeSourceItem {
  scopeLabel: "private" | "public"
  uploadedAtLabel: string
}

interface ManagerData {
  status: "loading" | "ready" | "error"
  items: DisplayItem[]
  quota: KnowledgeSourceQuota | null
  selectedFile: SelectedFile | null
  selectedScope: "private" | "public"
  idempotencyKey: string
  uploading: boolean
  quotaDisabled: boolean
  errorMessage: string
}

const INITIAL_DATA: ManagerData = {
  status: "loading",
  items: [],
  quota: null,
  selectedFile: null,
  selectedScope: "private",
  idempotencyKey: "",
  uploading: false,
  quotaDisabled: false,
  errorMessage: "",
}

Component({
  data: INITIAL_DATA,

  lifetimes: {
    attached() {
      void this.loadCollection()
    },
  },

  methods: {
    async loadCollection(preserveItems = false) {
      this.setData({
        status: preserveItems ? "ready" : "loading",
        errorMessage: "",
      })
      try {
        const collection = await fetchKnowledgeSources()
        this.applyCollection(collection)
      } catch (error) {
        const message =
          error instanceof KnowledgeSourceApiError
            ? error.message
            : "上传记录加载失败，请稍后重试"
        this.setData({
          status: preserveItems ? "ready" : "error",
          errorMessage: message,
        })
      }
    },

    applyCollection(collection: KnowledgeSourceCollection) {
      this.setData({
        status: "ready",
        items: displayItems(collection.items),
        quota: collection.quota,
        quotaDisabled: quotaExhausted(collection.quota),
        errorMessage: "",
      })
    },

    chooseFile() {
      if (this.data.uploading || this.data.quotaDisabled) {
        return
      }
      wx.chooseMessageFile({
        count: 1,
        type: "file",
        extension: ["md"],
        success: (result) => {
          const file = result.tempFiles[0]
          if (!file) {
            return
          }
          this.setData({
            selectedFile: {
              name: file.name,
              path: file.path,
              size: file.size,
              sizeLabel: formatFileSize(file.size),
            },
            selectedScope: "private",
            idempotencyKey: createIdempotencyKey(),
            errorMessage: "",
          })
        },
      })
    },

    selectScope(
      event: WechatMiniprogram.CustomEvent<
        Record<string, never>,
        Record<string, never>,
        {scope?: unknown}
      >,
    ) {
      const scope = event.currentTarget.dataset.scope
      if (scope === "private" || scope === "public") {
        this.setData({selectedScope: scope})
      }
    },

    async submitUpload() {
      const selectedFile = this.data.selectedFile
      if (
        selectedFile === null ||
        this.data.uploading ||
        this.data.quotaDisabled
      ) {
        return
      }
      this.setData({uploading: true, errorMessage: ""})
      try {
        const result = await uploadKnowledgeSource({
          filePath: selectedFile.path,
          originalFilename: selectedFile.name,
          scope: this.data.selectedScope.toUpperCase() as KnowledgeSourceScope,
          idempotencyKey: this.data.idempotencyKey,
        })
        const optimisticItems = displayItems([
          result.source,
          ...this.data.items,
        ])
        this.setData({
          items: optimisticItems,
          quota: result.quota,
          quotaDisabled: quotaExhausted(result.quota),
          selectedFile: null,
          selectedScope: "private",
          idempotencyKey: "",
        })
        await this.loadCollection(true)
      } catch (error) {
        const apiError =
          error instanceof KnowledgeSourceApiError ? error : null
        const quota = apiError?.quota ?? this.data.quota
        this.setData({
          errorMessage: apiError?.message ?? "上传失败，请稍后重试",
          quota,
          quotaDisabled:
            apiError?.code === "daily_upload_limit_reached" ||
            apiError?.code === "effective_source_limit_reached" ||
            (quota !== null && quotaExhausted(quota)),
        })
      } finally {
        this.setData({uploading: false})
      }
    },

    retryCollection() {
      void this.loadCollection()
    },
  },
})

function displayItems(items: KnowledgeSourceItem[]): DisplayItem[] {
  return sortNewestFirst(items).map((item) => ({
    ...item,
    scopeLabel: item.scope.toLowerCase() as "private" | "public",
    uploadedAtLabel: formatUploadTime(item.uploaded_at),
  }))
}
