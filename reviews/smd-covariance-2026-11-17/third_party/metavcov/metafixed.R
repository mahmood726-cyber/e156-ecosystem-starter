metafixed <- function(y, Slist) {
y <- as.matrix(y)
nay <- is.na(y)
k <- ncol(y)
m <- nrow(y)
X <- as.matrix(rep(1, m))

Xlist <- lapply(seq(m),function(i) diag(1,k)[!nay[i,],,drop=FALSE]%x%
                  X[i,,drop=FALSE])
ylist <- lapply(seq(m),function(i) y[i,][!nay[i,]])
nalist <- lapply(seq(m),function(i) nay[i,])

Ulist <- lapply(Slist,chol)
invUlist <- lapply(Ulist,function(U) backsolve(U,diag(ncol(U))))
invtUXlist <- mapply(function(invU,X) crossprod(invU,X),
                     invUlist,Xlist,SIMPLIFY=FALSE)
invtUylist <- mapply(function(invU,y) crossprod(invU,y),
                     invUlist,ylist,SIMPLIFY=FALSE)
invtUX <- do.call("rbind",invtUXlist)
invtUy <- do.call("rbind",invtUylist)
coef <- as.numeric(qr.solve(invtUX,invtUy))

qrinvtUX <- qr(invtUX)
R <- qr.R(qrinvtUX)
vcov <- tcrossprod(backsolve(R,diag(1,ncol(invtUX))))

Q <- drop(crossprod(invtUy-invtUX%*%coef))
df <- (m - 1)*k

fit <- list()
fit$Q <- Q
fit$df <- df
fit$coefficients <- matrix(coef, dimnames=list(colnames(y)))
fit$vcov <- vcov
fit$k <- k
class(fit) <- "metafixed"
fit
}


summary.metafixed <- function(object, ...){
  ci.level = 0.95
  fit = object
coef <- as.numeric(fit$coef)
coef.se <- sqrt(diag(fit$vcov))
zval <- coef/coef.se
zvalci <- qnorm((1 - ci.level)/2,lower.tail = FALSE)
pvalue <- 2*(1-pnorm(abs(zval)))
ci.lb <- coef-zvalci*coef.se
ci.ub <- coef+zvalci*coef.se
cilab <- paste(signif(ci.level,2)*100,"%ci.",c("lb","ub"),sep = "")

tab <- cbind(coef, coef.se, zval, pvalue, ci.lb, ci.ub)
dimnames(tab) <- list(rownames(fit$coef),
                           c("Estimate","Std. Error","z","Pr(>|z|)",cilab))
qtest <- list()
qtest$Q <- fit$Q
qtest$df <- fit$df
qtest$pvalue <- 1-pchisq(fit$Q,fit$df)
qtest$k <- fit$k
x <- list(coefficients = tab, qtest = qtest)
class(x) <- "summary.metafixed"
x
}

print.summary.metafixed <- function(x, ...){
digits <- 4
cat("Fixed-effects coefficients","\n",sep="")
signif <- symnum(x$coefficients[,"Pr(>|z|)"],corr=FALSE,na=FALSE,
                 cutpoints=c(0, 0.001,0.01,0.05,0.1,1),
                 symbols=c("***","**","*","."," "))
###########################################################################
# Summary table
#
tabletot <- formatC(x$coefficients,digits=digits,format="f")
tabletot <- cbind(tabletot,signif)
colnames(tabletot)[7] <- ""

print(tabletot,quote=FALSE,right=TRUE,print.gap=2)
cat("---\nSignif. codes: ",attr(signif,"legend"),"\n\n")
###########################################################################
# Q statistic and I-square
#
Q <- formatC(x$qtest$Q,digits = digits,format = "f")
pvalue <- formatC(x$qtest$pvalue, digits = digits, format="f")
I2 <- formatC(pmax((x$qtest$Q-x$qtest$df)/x$qtest$Q*100,1), digits = 1,format = "f")
cat(if(x$qtest$k==1) "Uni" else "Multi","variate ","Cochran Q-test for heterogeneity:","\n",sep="")
cat("Q = ",Q," (df = ",x$qtest$df,"), p-value = ",pvalue,"\n",sep="")
cat("I-square statistic = ",I2,"%","\n\n",sep="")
}

