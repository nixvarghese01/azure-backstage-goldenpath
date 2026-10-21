import { defaultComponentThemes } from '@backstage/theme';
import { withDefaults } from './theme';

describe('withDefaults', () => {
  it("keeps Backstage's default slots and adds ours on top", () => {
    const merged = withDefaults({ MuiTableCell: { styleOverrides: { head: { fontWeight: 600 } } } });
    const theme = { spacing: (...n: number[]) => n.map(x => `${x * 8}px`).join(' '), palette: { textSubtle: '#999' } };
    const root = (merged.MuiTableCell.styleOverrides!.root as Function)({ theme });
    const head = (merged.MuiTableCell.styleOverrides!.head as Function)({ theme });
    expect(root.verticalAlign).toBe('middle'); // Backstage's dense table cell survives
    expect(head).toMatchObject({ color: '#999', fontWeight: 600 }); // theirs plus ours
    expect(Object.keys(merged)).toEqual(expect.arrayContaining(Object.keys(defaultComponentThemes ?? {})));
  });
});
