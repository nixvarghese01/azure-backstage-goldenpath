import { createUnifiedTheme, defaultComponentThemes, palettes, type PageTheme } from '@backstage/theme';

/**
 * The portal's look: a calm, near-black dark theme (and a light one) in the style of current developer
 * tools. Thin borders instead of shadows, one violet accent, Inter, flat headers with a soft glow.
 */
const accent = { dark: '#8B7CF6', light: '#5B4BDB' };
const fontFamily = [
  '"Inter Variable"',
  'Inter',
  'ui-sans-serif',
  'system-ui',
  '-apple-system',
  '"Segoe UI"',
  'Roboto',
  'sans-serif',
].join(', ');

const status = {
  ok: '#22C55E',
  warning: '#F59E0B',
  error: '#EF4444',
  running: '#8B7CF6',
  pending: '#94A3B8',
  aborted: '#64748B',
};

/** Flat page headers: the page background with a soft accent glow, the same for every page type. */
function flatPages(background: string, glow: string, fontColor: string): Record<string, PageTheme> {
  const page: PageTheme = {
    colors: [background, background],
    shape: 'none',
    backgroundImage: `radial-gradient(900px 220px at 0% 0%, ${glow}, transparent 70%), linear-gradient(${background}, ${background})`,
    fontColor,
  };
  return Object.fromEntries(
    ['home', 'tool', 'service', 'website', 'library', 'other', 'app', 'apis', 'documentation', 'card'].map(id => [id, page]),
  );
}

type ComponentThemes = Record<string, { defaultProps?: object; styleOverrides?: Record<string, unknown> }>;

const resolve = (style: unknown, props: unknown) =>
  (typeof style === 'function' ? style(props) : style ?? {}) as Record<string, unknown>;

/**
 * Layers our component styles on top of Backstage's defaults. createUnifiedTheme merges per component
 * only, so an override would otherwise drop Backstage's own slots (dense tables, tab sizes, chip margins).
 */
export function withDefaults(overrides: ComponentThemes): ComponentThemes {
  const base = (defaultComponentThemes ?? {}) as ComponentThemes;
  const merged: ComponentThemes = { ...base };
  for (const [name, mine] of Object.entries(overrides)) {
    const theirs = base[name] ?? {};
    const slots = new Set([...Object.keys(theirs.styleOverrides ?? {}), ...Object.keys(mine.styleOverrides ?? {})]);
    const styleOverrides: Record<string, unknown> = {};
    for (const slot of slots) {
      styleOverrides[slot] = (props: unknown) => ({
        ...resolve(theirs.styleOverrides?.[slot], props),
        ...resolve(mine.styleOverrides?.[slot], props),
      });
    }
    merged[name] = {
      ...theirs,
      ...mine,
      defaultProps: { ...theirs.defaultProps, ...mine.defaultProps },
      styleOverrides,
    };
  }
  return merged;
}

function components(border: string, subtle: string): ComponentThemes {
  return {
    BackstageHeader: {
      styleOverrides: {
        header: { boxShadow: 'none', borderBottom: `1px solid ${border}`, padding: '28px 40px 20px' },
        title: { fontWeight: 650, letterSpacing: '-0.02em' },
        subtitle: { opacity: 0.75 },
        type: { textTransform: 'none', letterSpacing: 0, opacity: 0.7 },
      },
    },
    // Navigation links are not prose: no underline in the sidebar, underline only on hover elsewhere.
    BackstageSidebarItem: {
      styleOverrides: {
        root: { textDecoration: 'none', '&:hover': { textDecoration: 'none' } },
        label: { textDecoration: 'none', fontWeight: 500 },
      },
    },
    MuiLink: { defaultProps: { underline: 'hover' as const } },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: 'none' },
        rounded: { borderRadius: 12 },
        elevation1: { boxShadow: 'none', border: `1px solid ${border}` },
        elevation2: { boxShadow: 'none', border: `1px solid ${border}` },
      },
    },
    MuiCard: { styleOverrides: { root: { borderRadius: 12 } } },
    MuiCardHeader: { styleOverrides: { title: { fontWeight: 600, letterSpacing: '-0.01em' } } },
    MuiButton: {
      styleOverrides: {
        root: { textTransform: 'none', borderRadius: 8, fontWeight: 600 },
        contained: { boxShadow: 'none', '&:hover': { boxShadow: 'none' } },
      },
    },
    MuiChip: { styleOverrides: { root: { borderRadius: 6, fontWeight: 500 } } },
    MuiTab: { styleOverrides: { root: { textTransform: 'none', fontWeight: 500, minWidth: 72 } } },
    MuiTabs: { styleOverrides: { indicator: { height: 2, borderRadius: 2 } } },
    MuiOutlinedInput: { styleOverrides: { root: { borderRadius: 8 } } },
    MuiTableCell: {
      styleOverrides: {
        root: { borderBottom: `1px solid ${border}` },
        head: { fontWeight: 600, color: subtle, textTransform: 'none' },
      },
    },
    MuiDivider: { styleOverrides: { root: { backgroundColor: border } } },
  };
}

export const darkTheme = createUnifiedTheme({
  fontFamily,
  defaultPageTheme: 'home',
  pageTheme: flatPages('#0B0C10', 'rgba(139,124,246,0.22)', '#F5F6FA'),
  palette: {
    ...palettes.dark,
    type: 'dark',
    mode: 'dark',
    primary: { main: accent.dark },
    secondary: { main: '#22D3EE' },
    background: { default: '#0B0C10', paper: '#121419' },
    text: { primary: '#E7E9EE', secondary: '#9AA3B2' },
    divider: 'rgba(255,255,255,0.08)',
    border: 'rgba(255,255,255,0.08)',
    textSubtle: '#9AA3B2',
    textVerySubtle: '#6B7280',
    link: '#A99BFA',
    linkHover: '#C4BAFC',
    status,
    navigation: {
      background: '#0E1015',
      indicator: accent.dark,
      color: '#9AA3B2',
      selectedColor: '#FFFFFF',
      navItem: { hoverBackground: 'rgba(255,255,255,0.05)' },
      submenu: { background: '#121419' },
    },
    tabbar: { indicator: accent.dark },
  },
  components: withDefaults(components('rgba(255,255,255,0.08)', '#9AA3B2')) as never,
});

export const lightTheme = createUnifiedTheme({
  fontFamily,
  defaultPageTheme: 'home',
  pageTheme: flatPages('#FFFFFF', 'rgba(91,75,219,0.12)', '#0F172A'),
  palette: {
    ...palettes.light,
    type: 'light',
    mode: 'light',
    primary: { main: accent.light },
    secondary: { main: '#0891B2' },
    background: { default: '#F7F8FA', paper: '#FFFFFF' },
    text: { primary: '#0F172A', secondary: '#475569' },
    divider: '#E5E7EB',
    border: '#E5E7EB',
    textSubtle: '#475569',
    textVerySubtle: '#94A3B8',
    link: accent.light,
    linkHover: '#4335B8',
    status,
    navigation: {
      background: '#FFFFFF',
      indicator: accent.light,
      color: '#475569',
      selectedColor: '#0F172A',
      navItem: { hoverBackground: '#F1F2F6' },
      submenu: { background: '#F7F8FA' },
    },
    tabbar: { indicator: accent.light },
  },
  components: withDefaults(components('#E5E7EB', '#475569')) as never,
});
