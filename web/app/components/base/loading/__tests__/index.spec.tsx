import { render } from '@testing-library/react'
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

  it('contains MMB loading image and beer fill animation layer', () => {
    const { container } = render(<Loading />)

    const imageElement = container.querySelector('img.mmb-loading-image')
    const beerFillElement = container.querySelector('.mmb-beer-fill')

    expect(imageElement).toHaveAttribute('src', '/custom-assets/mmb-loading/mmb-bear-bottle-transparent.png')
    expect(beerFillElement).toBeInTheDocument()
  })

  it('handles undefined props correctly', () => {
    const { container } = render(Loading() as unknown as React.ReactElement)
    expect(container.firstChild).toHaveClass('flex w-full items-center justify-center')
  })
})
