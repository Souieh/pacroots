# Maintainer: Souieh
pkgname="pacroots"
pkgver=0.1.0
pkgrel=1
pkgdesc="Browse your explicit packages as a dependency tree, with what each one exclusively owns"
arch=('any')
url="https://github.com/souieh/pacroots"
license=('MIT')
depends=('python' 'pacman')
source=("$pkgname-$pkgver.tar.gz::$url/archive/v$pkgver.tar.gz")
sha256sums=('8a819764b47b9eccf1907138ea30dc3899e7cd89558291ce7a183fcd914d171f')

package() {
  cd "$pkgname-$pkgver"
  install -Dm755 main.py       "$pkgdir/usr/share/$pkgname/main.py"
  install -Dm644 template.html "$pkgdir/usr/share/$pkgname/template.html"
  install -d "$pkgdir/usr/bin"
  ln -s "../share/$pkgname/main.py" "$pkgdir/usr/bin/$pkgname"
  install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
  install -Dm644 LICENSE   "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
