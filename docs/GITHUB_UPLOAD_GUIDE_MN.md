# GitHub дээр анхны файлуудыг оруулах заавар

**Зорилтот repository:** https://github.com/Plasma742/tavantolgoi-dust-research

2026-11-04-ний анхны шалгалтаар repository **хоосон, Public** байсан. GitHub-ийн холбогдсон эрхэнд `push` зөвшөөрөл байхгүй тул эдгээр файлуудыг GitHub руу ChatGPT-ээс шууд бичиж чадаагүй. Энэ бол оруулахад бэлэн архив, GitHub дээр бодитоор байршуулсан хувилбар биш.

## Арга A — GitHub вэбээр оруулах

1. `tavantolgoi-dust-research-upload-ready.zip` файлыг компьютер дээрээ татаж задлаарай.
2. ZIP доторх `tavantolgoi-dust-research-starter` фолдер **доторх бүх файлыг** сонгоно (фолдерыг нь өөрийг нь нэг давхар түвшинд байрлуулахгүй).
3. Repository руу орж **uploading an existing file** эсвэл **Add file → Upload files** сонгоно.
4. README.md, CLAUDE.md, docs/, gee/, .github/, .gitignore, .env.example болон бусад файлыг бүтцээр нь upload хийнэ.
5. Commit message: `chore: initialize Tavan Tolgoi dust research platform`.
6. GitHub дээр `README.md`, `CLAUDE.md`, `docs/`, `gee/` зэрэг нь repository root-д харагдаж байгааг шалгаарай.

> GitHub-ийн интерфейс фолдерын бүтцийг upload хийхдээ өөрөөр зохион байгуулж болзошгүй. Файл бүрийг эхний түвшинд зөв байрлуулсан эсэхийг шалгаарай. Зөвхөн ZIP файлыг GitHub-д оруулах нь Claude-д файлуудыг шууд унших боломжтой repository бүтэц үүсгэхгүй.

## Арга B — Git ашиглах (илүү найдвартай)

```bash
git clone https://github.com/Plasma742/tavantolgoi-dust-research.git
cd tavantolgoi-dust-research
# Задалсан starter фолдерын ДОТОРХ бүх файлыг энд хуулна.
git add -A
git commit -m "chore: initialize Tavan Tolgoi dust research platform"
git branch -M main
git push -u origin main
```

## Чат дотроос шууд GitHub-д бичүүлэх

ChatGPT-ийн GitHub холболтыг энэ repository дээр `write`/`push` эрхтэй GitHub owner account эсвэл зохих GitHub App installation-тай холбоно. Дараа нь GitHub-ийн зөвшөөрлийг дахин шалгуулна. Нууц үг, personal access token, service-account key-г чат руу бүү илгээгээрэй.

## Репозиторийн нууцлал

Repository одоогоор Public байгаа. Хэрэв судалгааны эхний шатанд нууц байлгах бол GitHub owner эрхээр **Settings → General → Danger Zone → Change repository visibility → Private** сонгоно. Үүнийг өөрчлөхөд GitHub Pages, хамтран ажиллагч, deployment-ийн тохиргоонд нөлөөлж болдог тул тусад нь шалгана.

## Энэ багцын хязгаарлалт

Судалгааны шаардлага, архитектур, кодын туршилтын эхлэл байгаа ч жинхэнэ веб, backend, Earth Engine authentication хараахан хийгдээгүй. Claude дараагийн шатанд хэрэгжүүлж, бодит дата дээр баталгаажуулах ёстой.
