import sys
import os
from PIL import Image

def main():
    if len(sys.argv) < 3:
        print("使用方法: python3 script.py <path1> <dir1>")
        sys.exit(1)

    path1 = sys.argv[1]
    dir1 = sys.argv[2]

    if not os.path.isfile(path1):
        print(f"エラー: 基準となる画像が見つかりません: {path1}")
        sys.exit(1)

    if not os.path.isdir(dir1):
        print(f"エラー: 対象ディレクトリが見つかりません: {dir1}")
        sys.exit(1)

    # 基準画像のサイズ（幅, 高さ）を取得
    try:
        with Image.open(path1) as ref_img:
            target_size = ref_img.size
    except Exception as e:
        print(f"基準画像の読み込みに失敗しました: {e}")
        sys.exit(1)

    print(f"基準サイズ: {target_size[0]}x{target_size[1]} ({path1})")

    # dir1 内のすべてのPNG画像を対象にリサイズを実行
    count = 0
    for filename in os.listdir(dir1):
        if filename.lower().endswith('.png'):
            file_path = os.path.join(dir1, filename)
            if os.path.isfile(file_path):
                try:
                    with Image.open(file_path) as img:
                        # 強制的に同じサイズにリサイズ（アスペクト比は無視されます）
                        resized_img = img.resize(target_size, Image.Resampling.LANCZOS)
                        resized_img.save(file_path)
                    print(f"リサイズ完了: {file_path}")
                    count += 1
                except Exception as e:
                    print(f"処理失敗 ({file_path}): {e}")

    print(f"合計 {count} 件のPNG画像をリサイズしました。")

if __name__ == "__main__":
    main()
