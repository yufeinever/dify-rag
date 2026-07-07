import { render, screen } from '@testing-library/react'
import * as React from 'react'
import Loading from '../index'

describe('Loading Component', () => {
  it('renders correctly with default props', () => {
    const { container } = render(<Loading />)
    expect(container.firstChild).toHaveClass('flex w-full items-center justify-center')
    expect(container.firstChild).not.toHaveClass('h-full')
  })

  it('renders correctly with area type', () => {
    const { container } = render(<Loading type="area" />)
    expect(container.firstChild).not.toHaveClass('h-full')
  })

  it('renders correctly with app type', () => {
    const { container } = render(<Loading type="app" />)
    expect(container.firstChild).toHaveClass('h-full')
  })

  it('renders the MMB loading asset with an accessible status label', () => {
    const { container } = render(<Loading />)

    expect(screen.getByRole('status', { name: 'appApi.loading' })).toBeInTheDocument()
    expect(container.querySelector('.mmb-loading-asset')).toBeInTheDocument()
    expect(container.querySelector('.mmb-loading-image')).toHaveAttribute(
      'src',
      '/custom-assets/mmb-loading/mmb-bear-bottle-transparent.png',
    )
  })

  it('handles undefined props correctly', () => {
    const { container } = render(Loading() as unknown as React.ReactElement)
    expect(container.firstChild).toHaveClass('flex w-full items-center justify-center')
  })
})
