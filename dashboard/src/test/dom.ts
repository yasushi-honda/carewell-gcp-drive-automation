// テスト用: DOM の読み取りヘルパー
//
// happy-dom 12.x は、キー付きリストの並べ替えで要素を末尾へ「移動」すると、
// `children` / `querySelectorAll` が古い状態のまま（移動した要素が重複して見える）になる。
// 実 DOM（`childNodes`）は正しいため、並び順を検証する箇所では `childNodes` を直接たどる。

/** root 配下にある `/students/N…` へのリンクの日介番号を、文書順に返す */
export function linkedStudentIds(root: Node): string[] {
  const ids: string[] = [];
  const walk = (node: Node) => {
    node.childNodes.forEach((child) => {
      if (child.nodeType !== 1) return;
      const element = child as Element;
      const href = element.tagName === 'A' ? element.getAttribute('href') : null;
      if (href && href.startsWith('/students/N')) ids.push(href.replace('/students/', ''));
      walk(element);
    });
  };
  walk(root);
  return ids;
}
