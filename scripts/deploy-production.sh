#!/bin/bash
# Production Deployment Script for Firestore Schema Improvement
# 本番環境へのマイグレーションとデプロイを自動化

set -e  # エラー時に停止

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ログ関数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 環境変数チェック
check_environment() {
    log_info "環境変数を確認中..."

    if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
        export GOOGLE_CLOUD_PROJECT="carewell-automation"
        log_warning "GOOGLE_CLOUD_PROJECT を設定: $GOOGLE_CLOUD_PROJECT"
    fi

    if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/application_default_credentials.json"
        log_warning "GOOGLE_APPLICATION_CREDENTIALS を設定: $GOOGLE_APPLICATION_CREDENTIALS"
    fi

    log_success "環境変数確認完了"
}

# Step 1: Dry-run実行
run_dry_run() {
    log_info "===================================================="
    log_info "Step 1: マイグレーション Dry-run 実行"
    log_info "===================================================="
    echo ""

    python3 scripts/migrate_parent_documents.py --dry-run

    if [ $? -eq 0 ]; then
        log_success "Dry-run 完了"
    else
        log_error "Dry-run 失敗"
        exit 1
    fi

    echo ""
}

# Step 2: ユーザー確認（オプショナル、--yes で自動承認）
confirm_execution() {
    if [ "$AUTO_APPROVE" = true ]; then
        log_info "自動承認モード: マイグレーションを実行します"
        return 0
    fi

    echo ""
    log_warning "===================================================="
    log_warning "本番環境でマイグレーションを実行します"
    log_warning "===================================================="
    echo ""
    read -p "続行しますか? (yes/no): " -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
        log_info "キャンセルされました"
        exit 0
    fi
}

# Step 3: マイグレーション実行
run_migration() {
    log_info "===================================================="
    log_info "Step 2: マイグレーション実行"
    log_info "===================================================="
    echo ""

    python3 scripts/migrate_parent_documents.py --execute

    if [ $? -eq 0 ]; then
        log_success "マイグレーション完了"
    else
        log_error "マイグレーション失敗"
        log_error "ロールバックが必要な場合: python3 scripts/rollback_parent_documents.py --confirm"
        exit 1
    fi

    echo ""
}

# Step 4: バリデーション実行
run_validation() {
    log_info "===================================================="
    log_info "Step 3: バリデーション実行"
    log_info "===================================================="
    echo ""

    python3 scripts/migrate_parent_documents.py --validate-only

    if [ $? -eq 0 ]; then
        log_success "バリデーション完了"
    else
        log_error "バリデーション失敗"
        log_warning "file_count不整合がある場合: python3 scripts/fix_file_count.py --execute"
        exit 1
    fi

    echo ""
}

# Step 5: file_count確認
check_file_count() {
    log_info "===================================================="
    log_info "Step 4: file_count 確認"
    log_info "===================================================="
    echo ""

    python3 scripts/fix_file_count.py --dry-run

    if [ $? -eq 0 ]; then
        log_success "file_count 確認完了"
    else
        log_error "file_count 確認失敗"
        exit 1
    fi

    echo ""
}

# Step 6: GitHub Actions確認
check_github_actions() {
    log_info "===================================================="
    log_info "Step 5: GitHub Actions デプロイ状況確認"
    log_info "===================================================="
    echo ""

    if command -v gh &> /dev/null; then
        log_info "最新のGitHub Actions実行状況:"
        gh run list --limit 3
        echo ""

        log_info "最新のrunの詳細:"
        gh run view --log-failed

        log_success "GitHub Actions確認完了"
    else
        log_warning "gh コマンドが見つかりません。手動でGitHub Actionsを確認してください。"
        log_info "https://github.com/$(git remote get-url origin | sed -e 's/.*github.com[:/]\(.*\)\.git/\1/')/actions"
    fi

    echo ""
}

# Step 7: 最終確認
final_check() {
    log_info "===================================================="
    log_info "デプロイ完了サマリー"
    log_info "===================================================="
    echo ""

    log_success "✅ マイグレーション実行完了"
    log_success "✅ バリデーション完了"
    log_success "✅ file_count確認完了"
    log_success "✅ GitHub Actionsデプロイ確認完了"

    echo ""
    log_info "次のステップ:"
    log_info "  1. Cloud Runログを確認: gcloud logging read \"resource.type=cloud_run_revision\" --limit 20"
    log_info "  2. Firestoreコンソールで親ドキュメントを確認"
    log_info "  3. ファイルアップロードをテスト"

    echo ""
    log_info "問題が発生した場合のロールバック:"
    log_info "  python3 scripts/rollback_parent_documents.py --confirm"

    echo ""
}

# メイン処理
main() {
    log_info "Firestore Schema Improvement - 本番デプロイ開始"
    echo ""

    # コマンドライン引数の処理
    AUTO_APPROVE=false
    for arg in "$@"; do
        case $arg in
            --yes|-y)
                AUTO_APPROVE=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --yes, -y    自動承認（確認プロンプトをスキップ）"
                echo "  --help, -h   このヘルプを表示"
                echo ""
                echo "Examples:"
                echo "  $0              # 対話モード"
                echo "  $0 --yes        # 自動承認モード"
                exit 0
                ;;
        esac
    done

    # 各ステップを実行
    check_environment
    run_dry_run
    confirm_execution
    run_migration
    run_validation
    check_file_count
    check_github_actions
    final_check

    log_success "🎉 デプロイ完了！"
}

# スクリプト実行
main "$@"
