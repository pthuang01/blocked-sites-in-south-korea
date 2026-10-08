import os
import sys
import shutil
import argparse
from collections import Counter
from typing import List, Tuple, Set

# Windows 控制台 UTF-8 輸出相容處理
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def load_domains(file_path: str) -> List[str]:
    """讀取網域名稱清單，過濾空行並去除前後空白"""
    if not os.path.exists(file_path):
        print(f"[錯誤] 找不到檔案: {file_path}")
        return []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        domains = [line.strip().lower() for line in f if line.strip()]
    return domains

def save_domains(file_path: str, domains: List[str], backup: bool = True):
    """將網域名稱清單存回檔案，可選擇是否建立 .bak 備份"""
    if backup and os.path.exists(file_path):
        bak_path = file_path + ".bak"
        shutil.copyfile(file_path, bak_path)
        print(f"  [備份] 已建立備份檔案: {os.path.basename(bak_path)}")
    
    with open(file_path, "w", encoding="utf-8", newline="\r\n") as f:
        for domain in domains:
            f.write(f"{domain}\r\n")
    print(f"  [完成] 已成功寫入: {os.path.basename(file_path)} (目前筆數: {len(domains)} 筆)")

def find_internal_duplicates(domains: List[str]) -> Tuple[List[str], dict]:
    """檢查單一檔案內部重複項，保留首次出現順序"""
    counts = Counter(domains)
    duplicates = {domain: count for domain, count in counts.items() if count > 1}
    
    seen = set()
    deduped = []
    for d in domains:
        if d not in seen:
            seen.add(d)
            deduped.append(d)
            
    return deduped, duplicates

def analyze(list_path: str, kr_path: str):
    """分析並輸出兩檔案的重複狀況報告"""
    print("=" * 65)
    print("  網站封鎖清單重複項目檢查報告")
    print("=" * 65)

    list_domains = load_domains(list_path)
    kr_domains = load_domains(kr_path)

    _, list_dups = find_internal_duplicates(list_domains)
    _, kr_dups = find_internal_duplicates(kr_domains)

    set_list = set(list_domains)
    set_kr = set(kr_domains)
    common_domains = sorted(list(set_list & set_kr))

    print(f"\n【項目一：單檔內部重複檢查】")
    print(f"  * {os.path.basename(list_path)}:")
    print(f"      - 總筆數: {len(list_domains)} 筆")
    print(f"      - 獨立網域: {len(set_list)} 筆")
    print(f"      - 內部重複項目: {len(list_domains) - len(set_list)} 筆 (共 {len(list_dups)} 個不同網域)")
    if list_dups:
        print(f"      - 重複網域清單:")
        for dom, count in list_dups.items():
            print(f"          • {dom:<25} (出現 {count} 次)")

    print(f"\n  * {os.path.basename(kr_path)}:")
    print(f"      - 總筆數: {len(kr_domains)} 筆")
    print(f"      - 獨立網域: {len(set_kr)} 筆")
    print(f"      - 內部重複項目: {len(kr_domains) - len(set_kr)} 筆")
    if kr_dups:
        print(f"      - 重複網域清單:")
        for dom, count in kr_dups.items():
            print(f"          • {dom:<25} (出現 {count} 次)")

    print(f"\n【項目二：跨檔案重複檢查（兩檔案交集）】")
    print(f"  * 同時存在於兩檔案的共有網域: {len(common_domains)} 筆")
    if common_domains:
        sample_count = min(10, len(common_domains))
        print(f"  * 共有網域範例 (前 {sample_count} 筆):")
        for dom in common_domains[:sample_count]:
            print(f"      • {dom}")
        if len(common_domains) > sample_count:
            print(f"      ... 及其餘 {len(common_domains) - sample_count} 筆共有網域")

    print("\n" + "=" * 65)
    return list_domains, kr_domains, list_dups, kr_dups, common_domains

def execute_action(action: str, list_path: str, kr_path: str, output_merged: str, backup: bool):
    list_domains = load_domains(list_path)
    kr_domains = load_domains(kr_path)

    if action == "dedup-internal":
        print("\n>> 正在執行：移除各檔案內部重複...")
        deduped_list, _ = find_internal_duplicates(list_domains)
        deduped_kr, _ = find_internal_duplicates(kr_domains)
        save_domains(list_path, deduped_list, backup=backup)
        save_domains(kr_path, deduped_kr, backup=backup)
        print(">> 完成！各檔案內部重複項已清除。")

    elif action == "cross-dedup":
        print("\n>> 正在執行：清除內部重複，並從 list.txt 移除已在 kr.list 出現的網域...")
        deduped_list, _ = find_internal_duplicates(list_domains)
        deduped_kr, _ = find_internal_duplicates(kr_domains)
        kr_set = set(deduped_kr)
        filtered_list = [d for d in deduped_list if d not in kr_set]
        save_domains(list_path, filtered_list, backup=backup)
        save_domains(kr_path, deduped_kr, backup=backup)
        removed_count = len(deduped_list) - len(filtered_list)
        print(f">> 完成！從 list.txt 移除了 {removed_count} 筆與 kr.list 重疊的項目。")

    elif action == "merge":
        print("\n>> 正在執行：合併兩檔案為單一無重複清單...")
        seen = set()
        merged = []
        for d in list_domains + kr_domains:
            if d not in seen:
                seen.add(d)
                merged.append(d)
        merged.sort()
        save_domains(output_merged, merged, backup=False)
        print(f">> 完成！合併清單已輸出至: {os.path.basename(output_merged)} (總計 {len(merged)} 筆獨特網域)")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    default_list = os.path.join(base_dir, "list.txt")
    default_kr = os.path.join(base_dir, "kr.list")

    parser = argparse.ArgumentParser(description="檢查並清理 list.txt 與 kr.list 的重複項目")
    parser.add_argument("--list-file", default=default_list, help="指定 list.txt 路徑")
    parser.add_argument("--kr-file", default=default_kr, help="指定 kr.list 路徑")
    parser.add_argument("--action", choices=["check", "dedup-internal", "cross-dedup", "merge"], default=None,
                        help="指定操作: check(僅檢查), dedup-internal(移除單檔內部重複), cross-dedup(從list.txt移除與kr.list重疊者), merge(合併為一檔)")
    parser.add_argument("--output-merged", default=os.path.join(base_dir, "merged.txt"), help="合併輸出檔案路徑")
    parser.add_argument("--no-backup", action="store_true", help="修改原檔時不產生 .bak 備份檔")

    args = parser.parse_args()

    # 1. 先執行分析並呈現報告
    analyze(args.list_file, args.kr_file)

    backup = not args.no_backup

    # 2. 判斷後續動作
    if args.action:
        if args.action != "check":
            execute_action(args.action, args.list_file, args.kr_file, args.output_merged, backup)
    else:
        # 未指定動作且處於互動終端時詢問，否則顯示指引
        if sys.stdin.isatty():
            print("\n請選擇要執行的去重操作：")
            print("  [1] 移除各檔案內部自身重複（保留兩檔案獨立且只去重自己）")
            print("  [2] 跨檔案去重（從 list.txt 移除已在 kr.list 存在的重疊項目）")
            print("  [3] 合併為單一檔案 merged.txt（合併兩檔案並去重排序）")
            print("  [0] 僅查看報告，不修改任何檔案")
            choice = input("\n請輸入選項代碼 (0-3) [預設 0]: ").strip()
            
            choice_map = {
                "1": "dedup-internal",
                "2": "cross-dedup",
                "3": "merge"
            }
            if choice in choice_map:
                execute_action(choice_map[choice], args.list_file, args.kr_file, args.output_merged, backup)
            else:
                print("已結束，未更動任何檔案。")
        else:
            print("\n[使用提示] 如需移除重複項目，請指定 --action 參數：")
            print("  • 移除各檔內部重複:            python dedup.py --action dedup-internal")
            print("  • 從 list.txt 移除 kr.list 項目: python dedup.py --action cross-dedup")
            print("  • 合併為單一不重複清單:        python dedup.py --action merge")

if __name__ == "__main__":
    main()
