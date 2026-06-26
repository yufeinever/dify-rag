'use client'

import { cn } from '@langgenius/dify-ui/cn'
import {
  RiFolderOpenFill,
  RiFolderOpenLine,
} from '@remixicon/react'
import Link from '@/next/link'
import { useSelectedLayoutSegment } from '@/next/navigation'

type DocumentManagementNavProps = {
  className?: string
}

const DocumentManagementNav = ({
  className,
}: DocumentManagementNavProps) => {
  const selectedSegment = useSelectedLayoutSegment()
  const activated = selectedSegment === 'document-management'

  return (
    <Link
      href="/document-management"
      className={cn('group text-sm font-medium', activated && 'hover:bg-components-main-nav-nav-button-bg-active-hover bg-components-main-nav-nav-button-bg-active font-semibold shadow-md', activated ? 'text-components-main-nav-nav-button-text-active' : 'text-components-main-nav-nav-button-text hover:bg-components-main-nav-nav-button-bg-hover', className)}
    >
      {activated
        ? <RiFolderOpenFill className="size-4" />
        : <RiFolderOpenLine className="size-4" />}
      <div className="ml-2 max-[1024px]:hidden">
        文档管理
      </div>
    </Link>
  )
}

export default DocumentManagementNav
