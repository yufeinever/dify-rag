import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ToolsNav from '../index'

const mockUseSelectedLayoutSegment = vi.fn()
vi.mock('@/next/navigation', () => ({
  useSelectedLayoutSegment: () => mockUseSelectedLayoutSegment(),
}))

describe('ToolsNav', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render standard inactive state correctly', () => {
      mockUseSelectedLayoutSegment.mockReturnValue(null)

      render(<ToolsNav />)

      const link = screen.getByRole('link')
      expect(link).toHaveAttribute('href', '/tools')
      expect(screen.getByText('common.menus.tools')).toBeInTheDocument()

      expect(screen.getByTestId('icon-hammer-line')).toBeInTheDocument()
      expect(screen.queryByTestId('icon-hammer-fill')).not.toBeInTheDocument()

      expect(link).toHaveClass('group')

      const button = screen.getByText('common.menus.tools').closest('div')
      expect(button).toHaveClass('text-text-tertiary')
      expect(button).toHaveClass('hover:bg-state-base-hover')
    })

    it('should render active state correctly', () => {
      mockUseSelectedLayoutSegment.mockReturnValue('tools')

      render(<ToolsNav />)

      const link = screen.getByRole('link')

      expect(link).toHaveClass('group')

      const button = screen.getByText('common.menus.tools').closest('div')
      expect(button).toHaveClass('border-components-main-nav-nav-button-border')
      expect(button).toHaveClass('bg-components-main-nav-nav-button-bg-active')
      expect(button).toHaveClass('text-components-main-nav-nav-button-text')
      expect(button).toHaveClass('shadow-md')

      expect(screen.getByTestId('icon-hammer-fill')).toBeInTheDocument()
      expect(screen.queryByTestId('icon-hammer-line')).not.toBeInTheDocument()
    })
  })

  describe('Props', () => {
    it('should merge additional classNames', () => {
      mockUseSelectedLayoutSegment.mockReturnValue(null)
      render(<ToolsNav className="custom-test-class" />)

      const link = screen.getByRole('link')
      expect(link).toHaveClass('custom-test-class')
    })
  })
})
