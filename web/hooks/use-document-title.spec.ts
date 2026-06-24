import { renderHookWithSystemFeatures } from '@/__tests__/utils/mock-system-features'
/**
 * Test suite for useDocumentTitle hook
 *
 * This hook manages the browser document title with support for:
 * - Custom branding (when enabled in system features)
 * - Default "Dify" branding
 * - Pending state handling (prevents title flicker during loading)
 * - Page-specific titles with automatic suffix
 *
 * Title format: "[Page Title] - [Brand Name]"
 * If no page title: "[Brand Name]"
 */
import useDocumentTitle from './use-document-title'

/**
 * Test behavior when system features are still loading
 * Title should remain empty to prevent flicker
 */
describe('title should be empty if systemFeatures is pending', () => {
  it('document title should be empty if set title', () => {
    renderHookWithSystemFeatures(() => useDocumentTitle('test'), { systemFeatures: null })
    expect(document.title).toBe('')
  })

  it('document title should be empty if not set title', () => {
    renderHookWithSystemFeatures(() => useDocumentTitle(''), { systemFeatures: null })
    expect(document.title).toBe('')
  })
})

/**
 * Test default branding behavior
 * When custom branding is disabled, should use "MMB-AI" as the brand name
 */
describe('use default branding', () => {
  it('document title should be test-MMB-AI if set title', () => {
    renderHookWithSystemFeatures(() => useDocumentTitle('test'), {
      systemFeatures: { branding: { enabled: false } },
    })
    expect(document.title).toBe('test - MMB-AI')
  })

  it('document title should be MMB-AI if not set title', () => {
    renderHookWithSystemFeatures(() => useDocumentTitle(''), {
      systemFeatures: { branding: { enabled: false } },
    })
    expect(document.title).toBe('MMB-AI')
  })
})

/**
 * Test custom branding behavior
 * When custom branding is enabled, should use the configured application_title
 */
describe('ignore Dify branding fallback', () => {
  it('document title should still use MMB-AI when branding title is Dify', () => {
    renderHookWithSystemFeatures(() => useDocumentTitle('test'), {
      systemFeatures: { branding: { enabled: true, application_title: 'Dify' } },
    })
    expect(document.title).toBe('test - MMB-AI')
  })
})

describe('use specific branding', () => {
  it('document title should be test-Test if set title', () => {
    renderHookWithSystemFeatures(() => useDocumentTitle('test'), {
      systemFeatures: { branding: { enabled: true, application_title: 'Test' } },
    })
    expect(document.title).toBe('test - Test')
  })

  it('document title should be Test if not set title', () => {
    renderHookWithSystemFeatures(() => useDocumentTitle(''), {
      systemFeatures: { branding: { enabled: true, application_title: 'Test' } },
    })
    expect(document.title).toBe('Test')
  })
})
