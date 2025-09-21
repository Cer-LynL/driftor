'use client'

import { useState, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Upload, X, Image as ImageIcon } from 'lucide-react'
import { toast } from 'sonner'

interface ImageUploadProps {
  value?: string | string[]
  onChange: (value: string | string[]) => void
  multiple?: boolean
  maxFiles?: number
  accept?: string
  label?: string
  className?: string
}

export function ImageUpload({
  value,
  onChange,
  multiple = false,
  maxFiles = 5,
  accept = 'image/*',
  label = 'Upload Image',
  className = ''
}: ImageUploadProps) {
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const currentImages = Array.isArray(value) ? value : value ? [value] : []

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return

    // Check file limits
    if (multiple && currentImages.length + files.length > maxFiles) {
      toast.error(`Maximum ${maxFiles} images allowed`)
      return
    }

    if (!multiple && files.length > 1) {
      toast.error('Only one image allowed')
      return
    }

    setUploading(true)

    try {
      const uploadedUrls: string[] = []

      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        
        // Validate file size (max 5MB)
        if (file.size > 5 * 1024 * 1024) {
          toast.error(`File ${file.name} is too large. Maximum size is 5MB.`)
          continue
        }

        // Create FormData for upload
        const formData = new FormData()
        formData.append('file', file)

        // Upload to your preferred service (e.g., Supabase Storage, Cloudinary, etc.)
        // For now, we'll create a mock URL - replace with actual upload logic
        const mockUrl = URL.createObjectURL(file)
        uploadedUrls.push(mockUrl)
      }

      if (uploadedUrls.length > 0) {
        if (multiple) {
          onChange([...currentImages, ...uploadedUrls])
        } else {
          onChange(uploadedUrls[0])
        }
        toast.success(`${uploadedUrls.length} image(s) uploaded successfully`)
      }
    } catch (error) {
      console.error('Upload error:', error)
      toast.error('Failed to upload image(s)')
    } finally {
      setUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const removeImage = (indexOrUrl: number | string) => {
    if (multiple && Array.isArray(value)) {
      const newImages = currentImages.filter((_, index) => 
        typeof indexOrUrl === 'number' ? index !== indexOrUrl : _ !== indexOrUrl
      )
      onChange(newImages)
    } else {
      onChange(multiple ? [] : '')
    }
  }

  return (
    <div className={`space-y-4 ${className}`}>
      <Label>{label}</Label>
      
      {/* Upload Button */}
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading || (!multiple && currentImages.length >= 1)}
          className="flex items-center gap-2"
        >
          <Upload className="h-4 w-4" />
          {uploading ? 'Uploading...' : 'Choose Image'}
        </Button>
        
        {multiple && (
          <span className="text-sm text-gray-500">
            {currentImages.length}/{maxFiles} images
          </span>
        )}
      </div>

      <Input
        ref={fileInputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* Image Preview */}
      {currentImages.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {currentImages.map((imageUrl, index) => (
            <div key={index} className="relative group">
              <div className="aspect-square rounded-lg border-2 border-dashed border-gray-300 overflow-hidden">
                <img
                  src={imageUrl}
                  alt={`Upload ${index + 1}`}
                  className="w-full h-full object-cover"
                />
              </div>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                className="absolute -top-2 -right-2 h-6 w-6 rounded-full p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                onClick={() => removeImage(index)}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {currentImages.length === 0 && (
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
          <ImageIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500 mb-2">No images uploaded</p>
          <p className="text-sm text-gray-400">
            Click &quot;Choose Image&quot; to upload {multiple ? 'images' : 'an image'}
          </p>
        </div>
      )}
    </div>
  )
}
