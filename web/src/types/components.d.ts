import DictTag from '@/components/DictTag/index.vue'
import Pagination from '@/components/Pagination/index.vue'
import TreeSelect from '@/components/TreeSelect/index.vue'
import FileUpload from '@/components/FileUpload/index.vue'
import ImageUpload from '@/components/ImageUpload/index.vue'
import ImagePreview from '@/components/ImagePreview/index.vue'
import RightToolbar from '@/components/RightToolbar/index.vue'
import Editor from '@/components/Editor/index.vue'

declare module 'vue' {
  export interface GlobalComponents {
    DictTag: typeof DictTag
    Pagination: typeof Pagination
    TreeSelect: typeof TreeSelect
    FileUpload: typeof FileUpload
    ImageUpload: typeof ImageUpload
    ImagePreview: typeof ImagePreview
    RightToolbar: typeof RightToolbar
    Editor: typeof Editor
  }
}