import { useParams } from "react-router-dom";

export function WorkspacePage() {
  const { id } = useParams();
  return <main className="page-placeholder"><h1>简历工作台</h1><p>项目 {id} 正在载入。</p></main>;
}
